"""Membaca file ProTrack (.p2x) dari DSLIB dan menghitung nilai earned value per aktivitas per periode.

Aturan perhitungan mengikuti cara ProTrack/PMConverter (Ghent University):

* Biaya rencana aktivitas = biaya tetap + tarif per jam x durasi + biaya sumber daya.
* PV  : biaya rencana yang seharusnya sudah terpakai pada tanggal status, linear terhadap jam kerja.
* EV  : biaya rencana x persentase selesai (aktivitas selesai = 100% biaya rencana).
* AC  : biaya rencana untuk durasi aktual + deviasi biaya aktual yang dicatat di periode itu.

Waktu dihitung dalam jam kerja memakai kalender proyek (jam kerja harian, hari kerja, hari libur).
"""
from __future__ import annotations

import ast
import re
import zipfile
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path
import xml.etree.ElementTree as ET

import numpy as np

NOT_STARTED = datetime.max


def parse_date(text: str | None) -> datetime | None:
    """Tanggal ProTrack disimpan sebagai ddMMyyyyHHmm (12 digit) atau ddMMyyyy (8 digit).
    Menit dibulatkan ke jam terdekat, sama seperti ProTrack/PMConverter."""
    if not text or text == "0":
        return None
    t = text.strip()
    if len(t) == 12:
        d = datetime(int(t[4:8]), int(t[2:4]), int(t[:2]), int(t[8:10]))
        return d + timedelta(hours=1) if int(t[10:12]) >= 30 else d
    if len(t) == 8:
        return datetime(int(t[4:8]), int(t[2:4]), int(t[:2]))
    return None


class Calendar:
    """Kalender kerja proyek. Semua durasi dinyatakan dalam jam kerja."""

    def __init__(self, nonworking_hours=(), nonworking_days=(), holidays=()):
        self.hours = sorted(set(range(24)) - set(nonworking_hours))
        self.days = sorted(set(range(7)) - set(nonworking_days))
        if not self.hours or not self.days:
            raise ValueError("kalender tanpa jam kerja")
        mask = "".join("1" if d in self.days else "0" for d in range(7))
        self._mask = mask
        self._hol = np.array(sorted(set(holidays)), dtype="datetime64[D]")
        self.hours_per_day = len(self.hours)
        self._epoch = np.datetime64("1990-01-01")

    def is_workday(self, d: date) -> bool:
        return bool(np.is_busday(np.datetime64(d), weekmask=self._mask, holidays=self._hol))

    def index(self, t: datetime) -> int:
        """Jumlah jam kerja sejak epoch sampai awal jam t."""
        days = int(np.busday_count(self._epoch, np.datetime64(t.date()), weekmask=self._mask, holidays=self._hol))
        n = days * self.hours_per_day
        if self.is_workday(t.date()):
            n += sum(1 for h in self.hours if h < t.hour)
        return n

    def working_hours_between(self, a: datetime, b: datetime) -> int:
        return self.index(b) - self.index(a)

    def end_date(self, start: datetime, duration_h: int) -> datetime:
        """Akhir jam kerja terakhir sebuah aktivitas (dipakai untuk tanggal selesai rencana)."""
        target = self.index(start) + max(duration_h, 0)
        d = start.date()
        # lompat per hari sampai hari yang memuat jam kerja ke-target
        while True:
            day_start = datetime.combine(d, datetime.min.time())
            base = self.index(day_start)
            if self.is_workday(d) and base + self.hours_per_day >= target and base < target:
                k = target - base  # jam kerja ke-k pada hari ini
                return day_start + timedelta(hours=self.hours[k - 1] + 1)
            if base >= target:  # durasi 0: akhir jam kerja sebelumnya
                prev = d - timedelta(days=1)
                while not self.is_workday(prev):
                    prev -= timedelta(days=1)
                return datetime.combine(prev, datetime.min.time()) + timedelta(hours=self.hours[-1] + 1)
            d += timedelta(days=1)


@dataclass
class Resource:
    rid: int
    name: str
    renewable: bool
    cost_use: float
    cost_unit: float
    unit: str


@dataclass
class Activity:
    aid: int
    name: str
    start: datetime
    duration_h: int
    fixed_cost: float
    hourly_cost: float
    group: str = ""
    resources: list = field(default_factory=list)  # (Resource, demand, fixed_assignment)
    end: datetime | None = None
    total_cost: float = 0.0
    resource_cost: float = 0.0
    planned_work_h: float = 0.0  # jam-sumber daya terbarukan (orang/alat x jam)
    budget_resources: bool = True  # False: biaya sumber daya tidak masuk anggaran (lihat dataset.py)

    @property
    def var_cost(self) -> float:
        return self.duration_h * self.hourly_cost

    def finalize(self, cal: Calendar):
        self.end = cal.end_date(self.start, self.duration_h)
        self.planned_work_h = 0.0
        rc = 0.0
        for res, dem, fixed in self.resources:
            if res.renewable:
                rc += dem * (res.cost_use + res.cost_unit * self.duration_h)
                self.planned_work_h += dem * self.duration_h
            elif fixed:
                rc += res.cost_use + dem * res.cost_unit
            else:
                rc += res.cost_use + dem * res.cost_unit * self.duration_h
        self.resource_cost = rc
        self.total_cost = self.fixed_cost + self.var_cost + (rc if self.budget_resources else 0.0)

    # ---- nilai per periode -------------------------------------------------
    def planned_value(self, status: datetime, cal: Calendar) -> float:
        if status >= self.end:
            return self.total_cost
        if status <= self.start:
            return 0.0
        run = cal.working_hours_between(self.start, status)
        pv = self.fixed_cost + run * self.hourly_cost
        for res, dem, fixed in (self.resources if self.budget_resources else []):
            if res.renewable:
                pv += dem * (res.cost_use + res.cost_unit * run)
            elif fixed:
                pv += res.cost_use + dem * res.cost_unit
            else:
                pv += res.cost_use + dem * res.cost_unit * run
        return pv

    def earned_value(self, pct: float, started: bool, remaining_h: int) -> float:
        if remaining_h == 0:
            return self.total_cost
        if not started or pct < 1e-5:
            return 0.0
        f = pct / 100.0
        ev = self.fixed_cost + f * self.var_cost
        for res, dem, fixed in (self.resources if self.budget_resources else []):
            if res.renewable:
                ev += dem * res.cost_use + f * dem * res.cost_unit * self.duration_h
            elif fixed:
                ev += res.cost_use + f * dem * res.cost_unit
            else:
                ev += res.cost_use + f * dem * res.cost_unit * self.duration_h
        return ev

    def planned_actual_cost(self, started: bool, actual_h: int) -> float:
        if not started or actual_h <= 0:
            return 0.0
        pac = self.fixed_cost + actual_h * self.hourly_cost
        for res, dem, fixed in self.resources:
            if res.renewable:
                pac += dem * (res.cost_use + res.cost_unit * actual_h)
            elif fixed:
                pac += res.cost_use + dem * res.cost_unit
            else:
                pac += res.cost_use + dem * res.cost_unit * actual_h
        return pac


@dataclass
class Project:
    code: str
    name: str
    currency: str
    calendar: Calendar
    activities: dict
    resources: dict
    periods: list  # [(no, name, status_date, {aid: record})]

    def set_budget_resources(self, include: bool):
        for a in self.activities.values():
            a.budget_resources = include
            a.finalize(self.calendar)

    @property
    def resource_cost(self) -> float:
        return sum(a.resource_cost for a in self.activities.values())

    @property
    def bac(self) -> float:
        return sum(a.total_cost for a in self.activities.values())

    @property
    def start(self) -> datetime:
        return min(a.start for a in self.activities.values())

    @property
    def end(self) -> datetime:
        return max(a.end for a in self.activities.values())


def _txt(node, tag, default=None):
    n = node.find(tag)
    return n.text if n is not None and n.text is not None else default


def _read_xml(path: Path) -> ET.Element:
    if path.suffix == ".zip":
        with zipfile.ZipFile(path) as z:
            raw = z.read(z.namelist()[0])
    else:
        raw = path.read_bytes()
    return ET.fromstring(raw)


def _outline(list_node, groups, prefix, out):
    """Kumpulkan aktivitas yang ada di struktur WBS beserta nama grup level teratas."""
    for child in list(list_node):
        typ = int(_txt(child, "Type", "0"))
        data = int(_txt(child, "Data", "-1"))
        if typ == 1:
            name = prefix or (groups.get(data) or "").strip()
            sub = child.find("List")
            if sub is not None:
                _outline(sub, groups, name, out)
        elif typ == 2:
            out.setdefault(data, prefix)


def load_project(path: Path) -> Project:
    root = _read_xml(Path(path))
    code = re.match(r"C\d{4}-\d+", Path(path).name).group(0)
    name = (_txt(root, "NAME", "") or "").strip()
    currency = _txt(root.find("Settings"), "CurrencySymbol", "") if root.find("Settings") is not None else ""

    ag = root.find("Agenda")
    nwh = [int(h.text) for h in ag.findall("NonWorkingHours/Hour")] if ag is not None else []
    nwd = [int(d.text) for d in ag.findall("NonWorkingDays/Day")] if ag is not None else []
    hol = [parse_date(h.text).date() for h in ag.findall("Holidays/Holiday")] if ag is not None else []
    cal = Calendar(nwh, nwd, [h for h in hol if h])

    resources = {}
    for rn in root.iter("Resource"):
        if rn.find("FIELD0") is None:
            continue
        rid = int(_txt(rn, "FIELD0"))
        resources[rid] = Resource(rid, (_txt(rn, "FIELD1", "") or "").strip(), bool(int(_txt(rn, "FIELD769", "1"))),
                                  float(_txt(rn, "FIELD770", "0")), float(_txt(rn, "FIELD771", "0")), _txt(rn, "FIELD778", "") or "")

    acts = {}
    for an in root.findall("Activities/Activity"):
        aid = int(_txt(an, "UniqueID"))
        acts[aid] = Activity(aid, (_txt(an, "Name", "") or "").strip(), parse_date(_txt(an, "BaseLineStart")),
                             int(_txt(an, "BaseLineDuration", "0")), float(_txt(an, "FixedBaselineCost", "0")),
                             float(_txt(an, "BaselineCostByUnit", "0")))
    groups = {int(_txt(g, "UniqueID")): _txt(g, "Name", "") for g in root.findall("ActivityGroups/ActivityGroup")}
    in_wbs = {}
    ol = root.find("OutlineList/List")
    if ol is not None:
        _outline(ol, groups, "", in_wbs)
    acts = {k: v for k, v in acts.items() if k in in_wbs}
    for k, a in acts.items():
        a.group = in_wbs[k] or "(tanpa grup)"

    for ra in root.findall("ResourceAssignments/ResourceAssignment"):
        rid, aid = int(_txt(ra, "FIELD1025")), int(_txt(ra, "FIELD1024"))
        if rid in resources and aid in acts:
            res = resources[rid]
            fixed = bool(int(_txt(ra, "FIELD1027", "0"))) and not res.renewable
            acts[aid].resources.append((res, float(ast.literal_eval(_txt(ra, "FIELD1026", "0"))), fixed))
    for a in acts.values():
        a.finalize(cal)

    periods = []
    pairs = []
    for tl in root.findall("TrackingList"):
        pairs += list(zip(tl.findall("TrackingPeriod"), tl.findall("TProTrackActivities-1")))
    if pairs:
        for i, (h, b) in enumerate(pairs):
            status = parse_date(_txt(h, "EndDate"))
            recs = {}
            ids = b.findall("Activity")
            vals = b.findall("TProTrackActivityTracking-1")
            for idn, v in zip(ids, vals):
                aid = int(idn.text)
                if aid not in acts:
                    continue
                recs[aid] = dict(actual_start=parse_date(_txt(v, "ActualStart")),
                                 actual_h=int(_txt(v, "ActualDuration", "0")),
                                 actual_cost_dev=float(_txt(v, "ActualCostDev", "0")),
                                 remaining_h=int(_txt(v, "RemainingDuration", "0")),
                                 remaining_cost_dev=float(_txt(v, "RemainingCostDev", "0")),
                                 pct=float(_txt(v, "PercentageComplete", "0")) * 100)
            periods.append((i + 1, (_txt(h, "Name", "") or f"TP{i}").strip(), status, recs))
        periods.sort(key=lambda p: p[2])
        periods = [(k + 1, n, s, r) for k, (_, n, s, r) in enumerate(periods)]
    return Project(code, name, currency, cal, acts, resources, periods)


def activity_period_rows(p: Project):
    """Satu baris per aktivitas per periode pemantauan dengan PV, EV, AC dan jam kerja."""
    for no, pname, status, recs in p.periods:
        for aid, a in p.activities.items():
            r = recs.get(aid)
            if r is None:  # aktivitas tidak dilaporkan: dianggap belum mulai
                r = dict(actual_start=None, actual_h=0, actual_cost_dev=0.0, remaining_h=a.duration_h,
                         remaining_cost_dev=0.0, pct=0.0)
            started = r["actual_start"] is not None
            pac = a.planned_actual_cost(started, r["actual_h"])
            ev = a.earned_value(r["pct"], started, r["remaining_h"])
            frac = 1.0 if r["remaining_h"] == 0 else (r["pct"] / 100 if started else 0.0)
            yield dict(kode_proyek=p.code, periode=no, nama_periode=pname, tanggal_status=status,
                       id_aktivitas=aid, pv=a.planned_value(status, p.calendar), ev=ev,
                       ac=pac + r["actual_cost_dev"], persen_selesai=r["pct"],
                       mulai_aktual=r["actual_start"], durasi_aktual_jam=r["actual_h"], sisa_durasi_jam=r["remaining_h"],
                       jam_kerja_rencana=a.planned_work_h, jam_kerja_earned=a.planned_work_h * frac,
                       jam_kerja_aktual=sum(d * r["actual_h"] for res, d, _ in a.resources if res.renewable) if started else 0.0)
