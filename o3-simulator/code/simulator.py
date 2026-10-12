"""Cycle controller and recovery shared by the five pipeline stages."""
from copy import deepcopy
from .init import SimulationResult
from .issue import issue
from .exe import exe
from .mem import mem
from .wb import wb
from .commit import commit


class Simulator:
    def __init__(self, config, instructions, reg_int=None, reg_fp=None, memory=None,
                 branch_offset_mode="words"):
        config.validate()
        if branch_offset_mode not in ("words", "bytes"):
            raise ValueError("branch_offset_mode must be words or bytes")
        self.config = deepcopy(config)
        self.instructions = list(instructions)
        self.reg_int = list(reg_int) if reg_int is not None else [0] * 32
        self.reg_fp = list(reg_fp) if reg_fp is not None else [0.0] * 32
        self.memory = list(memory) if memory is not None else [0.0] * 256
        if (len(self.reg_int), len(self.reg_fp), len(self.memory)) != (32, 32, 256):
            raise ValueError("State must contain 32 integer, 32 FP, and 256 memory slots")
        self.reg_int[0] = 0
        self.branch_offset_mode = branch_offset_mode
        self.pc, self.next_seq, self.cycle = 0, 0, 0
        self.rob, self.history, self.lsq, self.tasks, self.results = [], [], [], [], []
        self.rs = {"int": [], "fp_add": [], "fp_mul": []}
        self.by_seq, self.rat, self.predictor = {}, {}, {}
        self.btb = [None] * 8
        self.fetch_resume, self.recovery_cycle = 0, -1
        self.memory_task, self.memory_free_after = None, -1
        self.events = []
        self.stats = {"issued": 0, "committed": 0, "issue_stalls": 0,
                      "mispredictions": 0, "replays": 0, "forwarded_loads": 0,
                      "btb_hits": 0}

    def squash_after(self, seq, next_pc, cycle, include=False, reason="branch"):
        discarded = [e for e in self.rob if e.seq > seq or (include and e.seq == seq)]
        for entry in discarded:
            entry.squashed = True
            entry.squash_cycle = cycle
            if entry.exe and entry.exe[-1] > cycle:
                entry.exe[-1] = cycle
            if entry.mem and entry.mem[-1] > cycle:
                entry.mem[-1] = cycle
        self.rob = [e for e in self.rob if not e.squashed]
        self.lsq = [e for e in self.lsq if not e.squashed]
        for unit in self.rs:
            self.rs[unit] = [e for e in self.rs[unit] if not e.squashed]
        self.tasks = [t for t in self.tasks if not t.entry.squashed]
        self.results = [r for r in self.results if not r.entry.squashed]
        if self.memory_task is not None and self.memory_task[0].squashed:
            self.memory_task = None
            self.memory_free_after = cycle
        # Rebuild from committed registers and surviving dynamic writers. This
        # retains older in-flight producers even if a younger writer replaced them.
        self.rat = {}
        for entry in self.rob:
            if entry.dest is not None and entry.dest != "R0":
                self.rat[entry.dest] = entry.seq
        self.pc = next_pc
        self.recovery_cycle = cycle + 1
        self.fetch_resume = cycle + 2
        self.events.append({"cycle": cycle, "reason": reason,
                            "trigger_seq": seq, "resume_cycle": cycle + 2,
                            "next_pc": next_pc, "squashed": [e.seq for e in discarded]})

    def check_memory_violation(self, store, cycle):
        violating = []
        for load in self.rob:
            if load.op != "ld" or load.seq <= store.seq or not load.mem or load.address != store.address:
                continue
            # A load forwarded from a later older store already sees the correct
            # newest value, so an earlier matching store cannot invalidate it.
            if load.forwarded_from is not None and load.forwarded_from >= store.seq:
                continue
            violating.append(load)
        if violating:
            first = min(violating, key=lambda e: e.seq)
            self.stats["replays"] += 1
            self.squash_after(first.seq, first.pc, cycle, include=True, reason="memory")

    def run(self, max_cycles=100000):
        if max_cycles < 1:
            raise ValueError("max_cycles must be positive")
        while self.rob or self.pc != len(self.instructions):
            if not self.rob and not 0 <= self.pc <= len(self.instructions):
                raise ValueError(f"Branch target outside instruction buffer: PC word {self.pc}")
            self.cycle += 1
            if self.cycle > max_cycles:
                raise RuntimeError(f"Simulation exceeded {max_cycles} cycles (possible infinite loop)")
            # Reverse stage order preserves clock boundaries. Wakeups and issue
            # values carry ready_cycle so WB consumers execute next cycle.
            commit(self, self.cycle)
            wb(self, self.cycle)
            mem(self, self.cycle)
            exe(self, self.cycle)
            issue(self, self.cycle)
        self.stats["squashed"] = sum(e.squashed for e in self.history)
        return SimulationResult(self.cycle, self.history, self.reg_int,
                                self.reg_fp, self.memory, dict(self.stats))
