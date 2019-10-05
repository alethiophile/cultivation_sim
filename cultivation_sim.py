#!/usr/bin/python3

# dear future me: this is a simulator for the Sefwen de-enchantment plot in
# Cultivation Quest, which requires a bunch of successful dice rolls under
# complex dynamics.

import random
from collections import defaultdict
from math import floor, ceil
from statistics import median, mean
import sys

def percentile(vals, percent):
    v = sorted(vals)
    k = (len(v) - 1) * percent
    f, c = floor(k), ceil(k)
    if f == c:
        return v[f]
    d0 = v[f] * (k - f)
    d1 = v[c] * (c - k)
    return d0 + d1

def dist2vals(dist):
    rv = []
    for i in dist:
        rv.extend([i] * dist[i])
    return rv

def print_dist(dist):
    min_disp = min(dist.keys())
    max_disp = max(dist.keys())
    vl = dist2vals(dist)
    print(f"Vals: {min_disp}, {percentile(vl, 0.25)}, "
          f"{median(vl)}, {percentile(vl, 0.75)}, "
          f"{max_disp}")
    print(f"Mean: {mean(vl)}")
    max_scale = max(dist.values())
    n_tot = sum(dist.values())
    cum_pct = 0.0
    for i in range(min_disp, max_disp + 1):
        scaled = floor(dist[i] / max_scale * 40)
        percent = round(dist[i] / n_tot * 100, 2)
        cum_pct += percent
        col_str = '#' * scaled + ' ' * (40 - scaled)
        print(f"{i: 3d}: {col_str} ({percent: 6.2f}% -> {cum_pct: 6.2f}%)")

def test_dist(func, n=1000):
    rs = defaultdict(lambda: 0)
    for i in range(n):
        r = func()
        rs[r] += 1
    print_dist(rs)

def diceroll(n, sides, bonus=0):
    """Returns a function that gives dice rolls for the given parameters."""
    return lambda x=0: sum(random.randint(1, sides) for i in range(n)) + bonus

def percent_chance(pc):
    """Returns a function that gives True or False at the given percent chance.

    """
    return lambda x=0: random.random() < (pc / 100)

class SimRun:
    potion_cooldown = 7
    pill_cooldown = 3
    growth_cooldown = 3
    stab_cult_cooldown = 1
    pill_overflow = percent_chance(5)

    growth_power = diceroll(1, 6)
    success_drain = diceroll(1, 6)
    success_stability_damage = diceroll(1, 4)
    failure_stability_damage = diceroll(3, 6)

    stability_cultivation = lambda self: diceroll(2, 6, bonus=26)() * 0.01
    stability_potion_gain = lambda self: 3
    stability_cutoff = 40

    removal_attempt = diceroll(2, 6, bonus=28)

    remove_during_withdrawal = False
    removal_attempt_withdrawal = diceroll(2, 6, bonus=23)

    remove_nopill_rp = False
    removal_attempt_nopill_rp = diceroll(2, 6, bonus=29)

    alchemy_minor = False
    alchemy_minor_damage = diceroll(1, 6)

    alchemy_major = False
    alchemy_major_damage = diceroll(2, 6)

    sefwen_will_mod = 13  # Soul + whatever her bonus is
    sefwen_fail_penalty = diceroll(1, 6)
    removal_fail_penalty = 5

    failure_insurance_ctr = 0
    insured_stability_damage = diceroll(1, 6)

    willpower_pills_policy = 'last'  # 'last', 'after-fail', 'first'
    willpower_pills_ctr = 0
    willpower_pills_bonus = 2

    def __init__(self, init_data={}, timed_adjust=None):
        self.attachments = 9
        self.power = 342
        self.stability = 88.35

        self.growth_ctr = 1
        self.potion_ctr = 1
        self.removal_ctr = 1
        self.stab_cult_ctr = 1
        self.alchemy_damage_ctr = 1

        self.day = 0
        self.remove_successes = 0
        self.remove_failures = 0

        self.new_attach_thres = (self.power // 20 + 1) * 20
        self.output = ""

        self.will_roll_failed = False

        self.timed_adjust = timed_adjust

        for i in init_data:
            setattr(self, i, init_data[i])

    @property
    def dc(self):
        return 25 + (self.power - 200) // 20

    def out(self, s):
        self.output += s + "\n"
        # print(s)

    @property
    def stabview(self):
        return round(self.stability, 5)

    def gain_stability(self, amt):
        self.stability += amt
        self.stability = min(self.stability, 100)

    def gain_power(self, amt):
        self.power += amt
        if self.power >= self.new_attach_thres:
            self.attachments += 1
            self.out(f"New attach, +1 = {self.attachments}")
            self.new_attach_thres += 20

    def sefwen_will_roll(self, escalate=False, wp_pill=False):
        rv = 0
        pg = 0
        rb = self.sefwen_will_mod
        c = 0
        if wp_pill and self.willpower_pills_ctr > 0:
            rb += self.willpower_pills_bonus
            self.willpower_pills_ctr -= 1
        while diceroll(2, 6, bonus=rb)() < 16 and pg < 30:
            pg += self.sefwen_fail_penalty()
            c += 1
            if escalate:
                rb -= 1
            # self.sefwen_will_mod += 3
            rv = self.removal_fail_penalty
            self.will_roll_failed = True
        if pg != 0:
            self.gain_power(pg)
            self.out(f"Sefwen will roll failed {c}x - +{pg} = {self.power}")
        return rv

    def brand_growth(self):
        g = self.growth_power()
        self.gain_power(g)
        self.growth_ctr = 1
        self.out(f"Brand grew, +{g} = {self.power}")
        self.sefwen_will_roll(True)

    def attempt_removal(self, nopill_rp=False, insure=True):
        if nopill_rp:
            self.out("remove nopill rp")
            roll = self.removal_attempt_nopill_rp()
        else:
            roll = self.removal_attempt()
        if not insure:
            roll += 5
        if insure and self.pill_overflow():
            self.out("Pill cooldown overflow")
            roll -= 1
        if insure:
            wp_pill = False
            if self.willpower_pills_policy == 'last':
                if self.attachments <= self.willpower_pills_ctr:
                    wp_pill = True
            elif self.willpower_pills_policy == 'first':
                wp_pill = True
            elif self.willpower_pills_policy == 'after-fail':
                if (self.will_roll_failed or
                    self.attachments <= self.willpower_pills_ctr):
                    wp_pill = True
            wp_pill = wp_pill and self.willpower_pills_ctr > 0
            if wp_pill:
                self.out(f"Using WP pill, {self.willpower_pills_ctr - 1} left")
            roll -= self.sefwen_will_roll(wp_pill=wp_pill)
        roll_dc = self.dc
        if roll >= roll_dc:
            self.attachments -= 1
            d = self.success_drain()
            self.power -= d
            s = self.success_stability_damage()
            self.stability -= s
            self.out(f"Removal success [{roll} - DC{roll_dc}], "
                     f"attach -1 = {self.attachments}, "
                     f"power -{d} = {self.power}, "
                     f"stab. -{s} = {self.stabview}")
            self.remove_successes += 1
        elif insure and self.failure_insurance_ctr > 0:
            s = self.insured_stability_damage()
            self.stability -= s
            self.failure_insurance_ctr -= 1
            self.out("Failure insurance used, "
                     f"{self.failure_insurance_ctr} left")
            self.out(f"Removal failure [{roll} - DC{roll_dc}] - insured, "
                     f"stab. -{s} = {self.stabview}")
            self.attempt_removal(nopill_rp, insure=False)
        else:
            s = self.failure_stability_damage()
            self.stability -= s
            self.out(f"Removal failure [{roll} - DC{roll_dc}], "
                     f"stab. -{s} = {self.stabview}")
            self.remove_failures += 1

    def run_day(self):
        self.day += 1
        self.out(f"Day {self.day}")
        if self.timed_adjust:
            self.timed_adjust(self)

        if self.day % 14 == 0:
            self.sefwen_will_mod -= 1

        if self.potion_ctr == self.potion_cooldown:
            g = self.stability_potion_gain()
            self.gain_stability(g)
            self.potion_ctr = 1
            self.out(f"Stab. pot., +{g} = {self.stabview}")
        else:
            self.potion_ctr += 1

            g = round(self.stability_cultivation(), 5)
            self.gain_stability(g)
            self.stab_cult_ctr = 1
            self.out(f"Stab. cult., +{g} = {self.stabview}")

        if self.growth_ctr == self.growth_cooldown:
            self.brand_growth()
        else:
            self.growth_ctr += 1

        if self.removal_ctr == self.pill_cooldown:
            self.attempt_removal(nopill_rp=self.remove_nopill_rp)
            self.removal_ctr = 1
            if self.alchemy_minor:
                if self.alchemy_major and self.alchemy_damage_ctr > 5:
                    s = self.alchemy_major_damage()
                    self.stability -= s
                    self.out(f"major alchemy damage, -{s} = {self.stabview}")
                elif self.alchemy_damage_ctr > 3:
                    s = self.alchemy_minor_damage()
                    self.stability -= s
                    self.out(f"minor alchemy damage, -{s} = {self.stabview}")
                self.alchemy_damage_ctr += 1
                if self.alchemy_major:
                    self.pill_cooldown = diceroll(1, 3)()
                else:
                    self.pill_cooldown = diceroll(1, 3, bonus=1)()
        else:
            self.removal_ctr += 1

        if self.removal_ctr == floor(self.pill_cooldown / 2):
            if self.remove_during_withdrawal:
                roll = self.removal_attempt_withdrawal()
                self.attempt_removal(roll)

    def run_sim(self, max_days=200):
        for i in range(max_days):
            self.run_day()
            if self.attachments == 0:
                success = True
                self.out("Removed all attachments, success")
                self.out(f"Stability {self.stabview}, "
                         f"final brand power {self.power}")
                break
            elif self.stability < self.stability_cutoff:
                success = False
                self.out(f"Stability below {self.stability_cutoff}, failure")
                self.out(f"Attachments {self.attachments}, power {self.power}")
                break
        else:
                success = False
        return {'success': success,
                'attachments': self.attachments,
                'day': self.day,
                'stability': self.stabview,
                'power': self.power,
                'n_successes': self.remove_successes,
                'n_failures': self.remove_failures,
                'output': self.output }


def run_many_sims(n=1000, data={}, timed_adjust=None, max_days=200):
    all_runs = []
    for i in range(n):
        a = SimRun(data, timed_adjust=timed_adjust)
        r = a.run_sim(max_days)
        all_runs.append(r)
    return all_runs

def print_runs_data(runs):
    success_rs = defaultdict(lambda: 0)
    stab_rs = defaultdict(lambda: 0)
    day_rs = defaultdict(lambda: 0)
    power_rs = defaultdict(lambda: 0)
    nsuc_rs = defaultdict(lambda: 0)
    nfail_rs = defaultdict(lambda: 0)
    for r in runs:
        success_rs[r['success']] += 1
        stab_rs[r['stability']] += 1
        day_rs[r['day']] += 1
        power_rs[r['power']] += 1
        nsuc_rs[r['n_successes']] += 1
        nfail_rs[r['n_failures']] += 1
    int_stab_rs = defaultdict(lambda: 0)
    for i in stab_rs:
        int_stab_rs[floor(i)] += stab_rs[i]
    suc_pct = round(success_rs[True] / len(runs) * 100, 2)
    print(f"{success_rs[True]} successes, "
          f"{success_rs[False]} failures ({suc_pct}%)")
    print("Final day:")
    print_dist(day_rs)
    print("End stability:")
    print_dist(int_stab_rs)
    print("End power:")
    print_dist(power_rs)
    print("Number successes:")
    print_dist(nsuc_rs)
    print("Number failures:")
    print_dist(nfail_rs)

def pc_4(a):
    """For passing to the adjust= argument of run_many_sims, sets pill cooldown
    time to 4 days.

    """
    a.pill_cooldown = 4

def pc_5(a):
    """For passing to the adjust= argument of run_many_sims, sets pill cooldown
    time to 5 days.

    """
    a.pill_cooldown = 5

def cooldown_4day(a):
    a.pill_cooldown = 4
    a.remove_nopill_rp = False

def cooldown_4day_badpill(a):
    a.pill_cooldown = 4
    a.pill_overflow = percent_chance(50)
    a.remove_nopill_rp = False


def cooldown_6day(a):
    a.power = 337
    a.pill_cooldown = 6
    a.pill_overflow = lambda: False

def nopill_rp(a):
    a.pill_cooldown = 2
    a.remove_nopill_rp = True
    a.pill_overflow = lambda: False

def nopill(a):
    a.power = 337
    a.pill_cooldown = 2
    a.remove_nopill_rp = True
    a.pill_overflow = lambda: False
    a.removal_attempt_nopill_rp = diceroll(2, 6, bonus=24)

def rp_first(a):
    if a.day == 1:
        nopill_rp(a)
        a.switched = False
    if a.attachments == 8 and not a.switched:
        cooldown_4day_badpill(a)
        a.switched = True

def odds(a):
    if a.day == 1:
        a.pill_cooldown = 5
        a.remove_nopill_rp = False
        a.pill_overflow = lambda: False
    elif a.attachments == 7:
        a.pill_cooldown = 4

minor_alchemy = {
    'alchemy_minor': True,
    'pill_overflow': lambda: False
}

major_alchemy = {
    'alchemy_minor': True,
    'alchemy_major': True,
    'pill_overflow': lambda: False
}

if __name__ == '__main__':
    n = 1000
    if len(sys.argv) > 1:
        n = int(sys.argv[1])
    l = run_many_sims(n)
    print_runs_data(l)
