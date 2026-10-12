"""Input parsing and typed state, replacing the starter's mutable tuple classes."""
from dataclasses import dataclass, field
from pathlib import Path
import re


@dataclass
class Config:
    int_rs: int = 2
    fp_add_rs: int = 3
    fp_mul_rs: int = 2
    lsq_size: int = 3
    int_ex: int = 1
    fp_add_ex: int = 3
    fp_mul_ex: int = 20
    ls_ex: int = 1
    mem_cycles: int = 4
    int_fus: int = 1
    fp_add_fus: int = 1
    fp_mul_fus: int = 1
    ls_fus: int = 1
    rob_entries: int = 128
    issue_width: int = 1

    def validate(self):
        for key, value in vars(self).items():
            if not isinstance(value, int) or value < 1:
                raise ValueError(f"{key} must be a positive integer")
        if self.issue_width > 4:
            raise ValueError("Issue width must be between 1 and 4")


@dataclass(frozen=True)
class Instruction:
    op: str
    dest: str | None = None
    src1: str | None = None
    src2: str | None = None
    immediate: int = 0
    text: str = ""


@dataclass
class Operand:
    value: int | float = 0
    tag: int | None = None
    ready_cycle: int = -1

    def available(self, cycle):
        return self.tag is None and self.ready_cycle < cycle


@dataclass
class ROBEntry:
    seq: int
    pc: int
    instruction: Instruction
    operand1: Operand
    operand2: Operand
    issue: int
    exe: list = field(default_factory=list)
    mem: list = field(default_factory=list)
    wb: int | None = None
    commit: int | None = None
    squashed: bool = False
    squash_cycle: int | None = None
    value: int | float | None = None
    address: int | None = None
    ready: bool = False
    predicted_next: int | None = None
    actual_next: int | None = None
    forwarded_from: int | None = None
    fault: str | None = None

    @property
    def op(self):
        return self.instruction.op

    @property
    def dest(self):
        return self.instruction.dest


@dataclass
class Task:
    entry: ROBEntry
    start: int
    end: int
    unit: str


@dataclass
class Result:
    entry: ROBEntry
    value: int | float
    completed: int


@dataclass
class SimulationResult:
    cycles: int
    history: list
    reg_int: list
    reg_fp: list
    memory: list
    stats: dict


_NUMBER = r"[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?"
_ASSIGNMENT = re.compile(rf"(?:(?P<reg>[rf]\d+)\s*=\s*(?P<rval>{_NUMBER})|mem\s*\[\s*(?P<addr>\d+)\s*\]\s*=\s*(?P<mval>{_NUMBER}))", re.I)


def _reg(token, kind):
    token = token.upper()
    if not re.fullmatch(rf"{kind}(?:[0-9]|[12][0-9]|3[01])", token):
        raise ValueError(f"Expected a {kind} register R/F0 through R/F31, got {token!r}")
    return token


def parse_instruction(text):
    tokens = re.sub(r",", " ", text).split()
    if not tokens:
        raise ValueError("Empty instruction")
    op = tokens[0].lower()
    if op in ("ld", "sd"):
        match = re.fullmatch(r"\s*(ld|sd)\s+([fF]\d+)\s*,?\s*([-+]?\d+)\s*\(\s*([rR]\d+)\s*\)\s*", text, re.I)
        if not match:
            raise ValueError(f"Invalid load/store syntax: {text}")
        fp, offset, base = _reg(match[2], "F"), int(match[3]), _reg(match[4], "R")
        return Instruction(op, fp if op == "ld" else None,
                           base if op == "ld" else fp,
                           None if op == "ld" else base, offset, text)
    if op in ("add", "sub", "addi", "add.d", "sub.d", "mult.d", "beq", "bne"):
        if len(tokens) != 4:
            raise ValueError(f"Expected three operands: {text}")
        if op in ("beq", "bne"):
            return Instruction(op, None, _reg(tokens[1], "R"), _reg(tokens[2], "R"), int(tokens[3]), text)
        kind = "F" if ".d" in op else "R"
        return Instruction(op, _reg(tokens[1], kind), _reg(tokens[2], kind),
                           None if op == "addi" else _reg(tokens[3], kind),
                           int(tokens[3]) if op == "addi" else 0, text)
    raise ValueError(f"Unsupported instruction: {text}")


def parse_input(path):
    config = Config()
    reg_int, reg_fp, memory = [0] * 32, [0.0] * 32, [0.0] * 256
    instructions = []
    unit_names = {
        "integer adder": ("int_rs", "int_ex", "int_fus"),
        "fp adder": ("fp_add_rs", "fp_add_ex", "fp_add_fus"),
        "fp multiplier": ("fp_mul_rs", "fp_mul_ex", "fp_mul_fus"),
        "load/store unit": ("lsq_size", "ls_ex", "mem_cycles", "ls_fus"),
    }
    for line_number, raw in enumerate(Path(path).read_text().splitlines(), 1):
        line = re.split(r"#|//|;", raw, maxsplit=1)[0].strip()
        if not line:
            continue
        try:
            low = line.lower()
            name = next((name for name in unit_names if low.startswith(name)), None)
            if name:
                fields = line[len(name):].split()
                keys = unit_names[name]
                if len(fields) == len(keys) - 1:
                    fields.append("1")
                if len(fields) != len(keys):
                    raise ValueError(f"Expected {len(keys)} hardware fields for {name}")
                for key, token in zip(keys, fields):
                    setattr(config, key, int(token))
                continue
            setting = re.fullmatch(r"(rob\s+entries|issue\s+width)\s*=\s*([-+]?\d+)", line, re.I)
            if setting:
                setattr(config, "rob_entries" if setting[1].lower().startswith("rob") else "issue_width", int(setting[2]))
                continue
            assignments = list(_ASSIGNMENT.finditer(line))
            if assignments:
                remaining = _ASSIGNMENT.sub("", line).replace(",", "").strip()
                if remaining:
                    raise ValueError(f"Unrecognized initialization text: {remaining}")
                for match in assignments:
                    if match["reg"]:
                        name = match["reg"].upper()
                        name = _reg(name, name[0])
                        value = float(match["rval"])
                        if name.startswith("R"):
                            if not value.is_integer():
                                raise ValueError("Integer register initialization must be an integer")
                            if name != "R0":
                                reg_int[int(name[1:])] = int(value)
                        else:
                            reg_fp[int(name[1:])] = value
                    else:
                        address = int(match["addr"])
                        if not 0 <= address < 256:
                            raise ValueError("Memory byte address must be in [0,255]")
                        memory[address] = float(match["mval"])
                continue
            instructions.append(parse_instruction(line))
        except ValueError as exc:
            raise ValueError(f"{path}:{line_number}: {exc}") from exc
    config.validate()
    return config, instructions, reg_int, reg_fp, memory
