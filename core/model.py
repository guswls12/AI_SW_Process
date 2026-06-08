"""
model.py — 순수 로직 레이어
  - C 함수 파싱 (주석 제거, 멀티라인 시그니처, 매크로 함수 지원)
  - diff 비교 및 변경 함수 목록 분석
  - 전역 영역 변경점 추출
UI·API 의존성 없음. 단독 테스트 가능.
"""

import re
import difflib
from dataclasses import dataclass, field
from typing import List, Optional


# ══════════════════════════════════════════════════════════════
#  데이터 클래스
# ══════════════════════════════════════════════════════════════
@dataclass
class FunctionInfo:
    """파싱된 C 함수 정보"""
    name: str
    signature: str
    start_line: int   # 0-based
    end_line: int     # 0-based (inclusive)
    body_lines: List[str] = field(default_factory=list)

    @property
    def full_text(self) -> str:
        return "\n".join(self.body_lines)


# ══════════════════════════════════════════════════════════════
#  주석 제거
# ══════════════════════════════════════════════════════════════
def _remove_comments(code: str) -> str:
    """C 스타일 주석 제거 (/* ... */ 및 // ...). 줄 번호는 유지."""
    result = []
    i = 0
    in_string = False
    string_char = ''

    while i < len(code):
        if not in_string and code[i] in ('"', "'"):
            in_string = True
            string_char = code[i]
            result.append(code[i]); i += 1; continue

        if in_string:
            if code[i] == '\\' and i + 1 < len(code):
                result.append(code[i:i+2]); i += 2; continue
            if code[i] == string_char:
                in_string = False
            result.append(code[i]); i += 1; continue

        # 블록 주석
        if code[i:i+2] == '/*':
            end = code.find('*/', i + 2)
            if end == -1:
                result.append('\n' * code[i:].count('\n'))
                break
            result.append('\n' * code[i:end+2].count('\n'))
            i = end + 2; continue

        # 라인 주석
        if code[i:i+2] == '//':
            end = code.find('\n', i)
            if end == -1: break
            result.append(' ')
            i = end; continue

        result.append(code[i]); i += 1

    return ''.join(result)


# ══════════════════════════════════════════════════════════════
#  함수 파싱 패턴
# ══════════════════════════════════════════════════════════════
_FUNC_START_RE = re.compile(
    r'^[\s]*'
    r'(?:'
    r'(?:static|inline|extern|volatile|const|register|unsigned|signed|'
    r'long|short|struct\s+\w+|union\s+\w+|enum\s+\w+|__\w+|'
    # 자동차 / 임베디드 코드에서 흔한 매크로 prefix
    r'INLINE|OS_INLINE|IFX_INLINE|LOCAL_INLINE|STATIC_INLINE|'
    r'STATIC|GLOBAL|LOCAL|EXTERN_FUNC|EXTERN|FORCE_INLINE|NOINLINE|'
    r'OS_FUNC|EE_FUNC|SLT_API|RTE_API|'
    r'WINAPI|CALLBACK|APIENTRY|EXPORT|__declspec\s*\([^)]*\)|'
    r'__attribute__\s*\(\([^)]*\)\))\s+)*'
    r'[\w][\w\s\*]*?'
    r'\b(\w+)\s*\('
)

_MACRO_FUNC_RE = re.compile(r'^[\s]*([A-Z][A-Z0-9_]*)\s*\(')

# AUTOSAR 스타일 함수 선언:
#   FUNC(Std_ReturnType, CtSpV4_DCM_IO_RC_If_CODE) App_Dcm_ShortTermAdj_F010(...)
#   FUNC_P2VAR(...) name(...)  /  LOCAL_INLINE FUNC(...) name(...) 등 변형 지원.
#
# prefix 부분은 임의 갯수의 대문자 매크로 / 표준 키워드를 허용해
# 'STATIC INLINE FUNC(...)', 'OS_INLINE LOCAL_INLINE FUNC(...)' 같은 조합도 처리.
# group(1) = 실제 함수 이름.
_AUTOSAR_FUNC_RE = re.compile(
    r'^[\s]*'
    r'(?:'
    r'(?:[A-Z][A-Z0-9_]*|static\s+inline|static|inline|extern)'
    r'\s+'
    r')*'
    r'FUNC(?:_P2VAR|_P2CONST|_P2FUNC|_CODE|_VAR|_CONST)?\s*'
    r'\([^)]*\)\s*'
    r'(\w+)\s*\('
)

_NOT_MACRO_FUNC = {
    'IF', 'ELSE', 'ELIF', 'ENDIF', 'IFDEF', 'IFNDEF',
    'DEFINE', 'INCLUDE', 'PRAGMA', 'ERROR', 'WARNING',
    'UNDEF', 'DEFINED',
}

_NOT_FUNC = {
    'if', 'else', 'for', 'while', 'do', 'switch', 'return',
    'sizeof', 'typedef', 'define', 'ifdef', 'ifndef', 'endif',
    'include', 'pragma', 'elif', 'case', 'default', 'goto',
}


# ══════════════════════════════════════════════════════════════
#  단일 함수 파싱 시도
# ══════════════════════════════════════════════════════════════
def _try_parse_function_at(
    cleaned_lines: List[str],
    start: int,
    original_lines: List[str],
) -> Optional[FunctionInfo]:
    """cleaned_lines[start] 부터 함수 정의가 시작되는지 판별."""
    line = cleaned_lines[start].strip()
    if not line or line.startswith('#') or line.startswith('typedef'):
        return None

    # 멀티라인 시그니처: '(' 가 없으면 다음 7줄까지 합쳐서 매칭
    # (AUTOSAR 처럼 반환 타입 매크로 + 함수 이름이 여러 줄로 나뉜 경우 대비)
    merged = cleaned_lines[start]
    if '(' not in merged:
        for k in range(start + 1, min(start + 8, len(cleaned_lines))):
            merged = merged + ' ' + cleaned_lines[k].strip()
            if '(' in merged:
                break

    # 함수 이름 추출
    # ① AUTOSAR FUNC(returnType, memClass) name(...) 패턴 먼저 시도
    is_autosar = False
    autosar_m = _AUTOSAR_FUNC_RE.match(merged)
    if autosar_m:
        func_name = autosar_m.group(1)
        if func_name not in _NOT_FUNC:
            is_autosar = True
            is_macro = False
            m = None  # 다른 분기에서 사용 안 함
    # ② 일반 함수 / 매크로 함수 패턴
    if not is_autosar:
        m = _FUNC_START_RE.match(merged)
        is_macro = False
        if not m:
            m = _MACRO_FUNC_RE.match(merged)
            if not m:
                return None
            if m.group(1) in _NOT_MACRO_FUNC:
                return None
            is_macro = True
            func_name = m.group(1)
        else:
            func_name = m.group(1)
            if func_name in _NOT_FUNC:
                return None

    # 매크로 함수: 첫 번째 인자를 이름에 포함
    if is_macro:
        paren_start = merged.find('(')
        if paren_start >= 0:
            inner = merged[paren_start+1:]
            first_arg = ''
            depth = 0
            for ch in inner:
                if ch == '(':
                    depth += 1; first_arg += ch
                elif ch == ')':
                    if depth == 0: break
                    depth -= 1; first_arg += ch
                elif ch == ',' and depth == 0:
                    break
                else:
                    first_arg += ch
            first_arg = first_arg.strip()
            if first_arg and first_arg.replace('_', '').isalnum():
                func_name = f"{m.group(1)}({first_arg})"

    # ')' 위치 탐색 (괄호 짝 맞추기)
    # AUTOSAR 의 'FUNC(returnType, memClass) name(...)' 형태는 첫 매크로 짝을
    # 건너뛰어야 진짜 함수 시그니처 끝을 찾을 수 있다.
    paren_depth = 0
    found_open = False
    # AUTOSAR 이면 처음 짝맞는 () 한 쌍은 매크로 부분이므로 skip
    macro_pairs_to_skip = 1 if is_autosar else 0
    pairs_skipped = 0
    i = start
    while i < len(cleaned_lines):
        for ch in cleaned_lines[i]:
            if ch == '(':
                paren_depth += 1
                if pairs_skipped >= macro_pairs_to_skip:
                    found_open = True
            elif ch == ')':
                paren_depth -= 1
                if paren_depth == 0:
                    if pairs_skipped < macro_pairs_to_skip:
                        # AUTOSAR FUNC(...) 매크로의 닫는 ')' — 건너뜀
                        pairs_skipped += 1
                        # found_open 은 아직 False 유지 (다음 '(' 부터 시작)
                    elif found_open:
                        break
        if found_open and paren_depth == 0 and pairs_skipped >= macro_pairs_to_skip:
            break
        i += 1

    if not found_open or paren_depth != 0:
        return None

    sig_end_line = i

    # ')' 뒤에 '{' 탐색 — 프로토타입(`;` 가 `)` 바로 뒤) vs 정의(`{`) 구분.
    # K&R 스타일 ( `int foo(a, b) int a; int b; { ... }` ) 에서 중간의 `;`
    # 때문에 false negative 가 나지 않도록, `;` 가 `)` 직후에 오는 경우만
    # 프로토타입으로 판정. 탐색 범위는 8줄로 확장(긴 K&R 선언 대비).
    brace_line = None
    for j in range(sig_end_line, min(sig_end_line + 8, len(cleaned_lines))):
        if j == sig_end_line:
            # 시그니처 종료 라인 — ')' 직후가 ';' 면 프로토타입 확정
            line_j = cleaned_lines[j]
            pp = line_j.rfind(')')
            after_paren = line_j[pp+1:].lstrip() if pp >= 0 else line_j
            if after_paren.startswith(';'):
                return None  # 프로토타입
        if '{' in cleaned_lines[j]:
            brace_line = j
            break

    if brace_line is None:
        return None

    # 대응하는 '}' 탐색
    brace_depth = 0
    end_line = None
    for j in range(brace_line, len(cleaned_lines)):
        for ch in cleaned_lines[j]:
            if ch == '{': brace_depth += 1
            elif ch == '}':
                brace_depth -= 1
                if brace_depth == 0:
                    end_line = j; break
        if end_line is not None:
            break

    if end_line is None:
        return None

    body = original_lines[start:end_line + 1]
    signature = ' '.join(
        original_lines[k].strip()
        for k in range(start, min(brace_line + 1, end_line + 1))
    )

    return FunctionInfo(
        name=func_name,
        signature=signature,
        start_line=start,
        end_line=end_line,
        body_lines=body,
    )


# ══════════════════════════════════════════════════════════════
#  전체 코드에서 함수 목록 파싱
# ══════════════════════════════════════════════════════════════
def parse_c_functions(code: str) -> List[FunctionInfo]:
    """
    C 코드에서 함수 정의 목록을 추출한다.
    주석 제거 후 파싱하므로 주석 내 {}에 의한 오탐을 방지한다.
    """
    lines = code.splitlines()
    cleaned_lines = _remove_comments(code).splitlines()

    # 줄 수가 다를 경우 패딩
    while len(cleaned_lines) < len(lines):
        cleaned_lines.append('')

    functions: List[FunctionInfo] = []
    i = 0
    while i < len(cleaned_lines):
        fi = _try_parse_function_at(cleaned_lines, i, lines)
        if fi:
            functions.append(fi)
            i = fi.end_line + 1
        else:
            i += 1

    # ── 후처리: 함수 사이의 공백/주석-only 줄을 이전 함수에 흡수 ────
    # 함수 닫는 '}' 바로 뒤의 빈 줄·주석-only 줄이 '전역 영역' 으로 잡혀
    # 변경점 분류가 어색해지는 문제를 줄임. cleaned_lines 는 주석 제거된
    # 상태라 주석-only 줄은 빈 문자열로 보임.
    for idx, fi in enumerate(functions):
        next_start = (functions[idx + 1].start_line
                      if idx + 1 < len(functions) else len(lines))
        j = fi.end_line + 1
        while j < next_start:
            stripped = cleaned_lines[j].strip() if j < len(cleaned_lines) else ''
            if stripped == '':
                fi.end_line = j
                j += 1
            else:
                break

    return functions


# ══════════════════════════════════════════════════════════════
#  전역 영역 추출
# ══════════════════════════════════════════════════════════════
def _extract_global_lines(code: str, functions: List[FunctionInfo]) -> List[str]:
    """함수 영역을 제외한 전역 라인 추출 (#define, #include, 전역 변수 등)."""
    lines = code.splitlines()
    func_ranges: set = set()
    for f in functions:
        for ln in range(f.start_line, f.end_line + 1):
            func_ranges.add(ln)
    return [line for i, line in enumerate(lines) if i not in func_ranges]


# ══════════════════════════════════════════════════════════════
#  함수/전역 단위 diff 생성 (내부용)
# ══════════════════════════════════════════════════════════════
def _make_global_diff(old_globals: List[str], new_globals: List[str]) -> List[str]:
    """전역 영역 diff. 빈 줄만 다른 경우는 무시."""
    if [l for l in old_globals if l.strip()] == [l for l in new_globals if l.strip()]:
        return []

    result = ["  ── 전역 영역 변경점 ──"]
    matcher = difflib.SequenceMatcher(None, old_globals, new_globals)
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == 'equal':
            lines = old_globals[i1:i2]
            if len(lines) > 6:
                for line in lines[:2]:  result.append(f"  {line}")
                result.append(f"  ... ({len(lines) - 4}줄 생략) ...")
                for line in lines[-2:]: result.append(f"  {line}")
            else:
                for line in lines: result.append(f"  {line}")
        elif tag == 'replace':
            for line in old_globals[i1:i2]: result.append(f"- {line}")
            for line in new_globals[j1:j2]: result.append(f"+ {line}")
        elif tag == 'delete':
            for line in old_globals[i1:i2]: result.append(f"- {line}")
        elif tag == 'insert':
            for line in new_globals[j1:j2]: result.append(f"+ {line}")
    return result


def _find_func_by_lineno(func_list: List[FunctionInfo],
                         lineno_0: int) -> Optional[FunctionInfo]:
    """0-based lineno 가 속한 FunctionInfo 반환."""
    for fi in func_list:
        if fi.start_line <= lineno_0 <= fi.end_line:
            return fi
    return None


# ══════════════════════════════════════════════════════════════
#  공개 API — diff_func_analysis
# ══════════════════════════════════════════════════════════════
def diff_func_analysis(old_lines: list, new_lines: list) -> list:
    """
    수정 전/후 코드를 비교하여 변경된 함수 목록을 반환한다.

    반환값: [(fn, first_ri, decl, changes, existence_flag), ...]
      fn             : 함수 이름 ("__global__" 은 전역 영역)
      first_ri       : diff row 최초 인덱스 (DiffView 스크롤용)
      decl           : 함수 선언 줄
      changes        : [(row_idx, tag, lineno), ...]
      existence_flag : "new" | "deleted" | "modified" | "global"
    """
    old_code = "\n".join(old_lines)
    new_code = "\n".join(new_lines)

    old_func_list = parse_c_functions(old_code)
    new_func_list = parse_c_functions(new_code)
    old_funcs = {f.name: f for f in old_func_list}
    new_funcs  = {f.name: f for f in new_func_list}

    # ── difflib row 목록 생성 (DiffView 스크롤 위치 계산용) ──
    matcher = difflib.SequenceMatcher(None, old_lines, new_lines, autojunk=False)
    rows: list = []
    on = nn = 0
    for op, a0, a1, b0, b1 in matcher.get_opcodes():
        if op == "equal":
            for i in range(a1 - a0):
                on += 1; nn += 1
                rows.append(("equal", on, old_lines[a0+i], nn, new_lines[b0+i]))
        elif op == "replace":
            oc = old_lines[a0:a1]; nc = new_lines[b0:b1]
            for i in range(max(len(oc), len(nc))):
                o = oc[i] if i < len(oc) else None
                n = nc[i] if i < len(nc) else None
                if o is not None: on += 1
                if n is not None: nn += 1
                rows.append(("replace",
                             on if o is not None else None, o or "",
                             nn if n is not None else None, n or ""))
        elif op == "delete":
            for i in range(a1 - a0):
                on += 1
                rows.append(("delete", on, old_lines[a0+i], None, ""))
        elif op == "insert":
            for i in range(b1 - b0):
                nn += 1
                rows.append(("insert", None, "", nn, new_lines[b0+i]))

    # ── 각 변경 row 를 함수 이름에 매핑 ──
    fn_to_rows: dict = {}
    for ri, (tag, ono, _o, nno, _n) in enumerate(rows):
        if tag == "equal":
            continue

        fn = None
        if nno:
            fi = _find_func_by_lineno(new_func_list, min(nno, len(new_lines)) - 1)
            fn = fi.name if fi else None
        if fn is None and ono:
            fi = _find_func_by_lineno(old_func_list, min(ono, len(old_lines)) - 1)
            fn = fi.name if fi else None
        if fn is None:
            fn = "__global__"

        if fn not in fn_to_rows:
            fn_to_rows[fn] = []
        # 표시 줄 번호: insert/replace → 새 파일 기준(nno), delete → 옛 파일 기준(ono)
        # replace 에서 nno 없는 여분 옛 줄은 스킵 → 역전 범위("줄 177~164") 버그 방지
        lno = nno if tag in ("insert", "replace") else ono
        if lno is None:
            continue
        fn_to_rows[fn].append((ri, tag, lno))

    result = []

    # ── 전역 영역 ──
    old_globals = _extract_global_lines(old_code, old_func_list)
    new_globals = _extract_global_lines(new_code, new_func_list)
    if old_globals != new_globals:
        rows_g   = fn_to_rows.get("__global__", [])
        first_ri = rows_g[0][0] if rows_g else 0
        result.append(("__global__", first_ri, "전역 영역", rows_g, "global"))

    # ── 함수 영역 ──
    all_names = list(dict.fromkeys(
        [f.name for f in old_func_list] + [f.name for f in new_func_list]))

    for name in all_names:
        old_f = old_funcs.get(name)
        new_f = new_funcs.get(name)

        # 내용 동일하면 스킵
        if old_f and new_f and old_f.full_text == new_f.full_text:
            continue

        changes  = fn_to_rows.get(name, [])
        first_ri = changes[0][0] if changes else 0

        if old_f and new_f:
            decl = new_f.signature
            flag = "modified"
        elif new_f and not old_f:
            decl = new_f.signature
            flag = "new"
            if not changes:
                changes = [(0, "insert", new_f.start_line + 1)]
        else:
            decl = old_f.signature
            flag = "deleted"
            if not changes:
                changes = [(0, "delete", old_f.start_line + 1)]

        result.append((name, first_ri, decl, changes, flag))

    return result


# ══════════════════════════════════════════════════════════════
#  공개 API — 유틸리티
# ══════════════════════════════════════════════════════════════
def strip_comments_from_lines(lines: list) -> list:
    """라인 리스트에서 C 스타일 주석을 제거한다. 줄 번호/개수는 보존."""
    code = "\n".join(lines)
    stripped = _remove_comments(code).splitlines()
    # 줄 수 보정 (만약 차이가 생기면 빈 줄로 패딩)
    while len(stripped) < len(lines):
        stripped.append("")
    # trailing space 제거 (예: "code(); // comment" → "code();")
    return [line.rstrip() for line in stripped[:len(lines)]]


def build_unified_diff(old_lines: list, new_lines: list,
                       from_file: str = "before",
                       to_file:   str = "after") -> str:
    """AI 입력용 unified diff 문자열."""
    return "\n".join(difflib.unified_diff(
        old_lines, new_lines,
        fromfile=from_file, tofile=to_file, lineterm=""))


def diff_stats(old_lines: list, new_lines: list) -> tuple:
    """(추가, 삭제, 수정) 줄 수."""
    matcher = difflib.SequenceMatcher(None, old_lines, new_lines, autojunk=False)
    n_add = n_del = n_mod = 0
    for op, a0, a1, b0, b1 in matcher.get_opcodes():
        if op == "insert":    n_add += b1 - b0
        elif op == "delete":  n_del += a1 - a0
        elif op == "replace": n_mod += max(a1 - a0, b1 - b0)
    return n_add, n_del, n_mod


# ══════════════════════════════════════════════════════════════
#  ChangedFunction 데이터클래스
# ══════════════════════════════════════════════════════════════
@dataclass
class ChangedFunction:
    """변경이 감지된 함수 + diff 결과"""
    name: str
    diff_lines: List[str] = field(default_factory=list)


# ══════════════════════════════════════════════════════════════
#  함수 단위 diff 생성
# ══════════════════════════════════════════════════════════════
def _make_function_diff(old_f: FunctionInfo, new_f: FunctionInfo) -> List[str]:
    result = [f"  ── 변경된 함수: {new_f.name} ──"]
    matcher = difflib.SequenceMatcher(None, old_f.body_lines, new_f.body_lines)
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == 'equal':
            for line in old_f.body_lines[i1:i2]:
                result.append(f"  {line}")
        elif tag == 'replace':
            for line in old_f.body_lines[i1:i2]: result.append(f"- {line}")
            for line in new_f.body_lines[j1:j2]: result.append(f"+ {line}")
        elif tag == 'delete':
            for line in old_f.body_lines[i1:i2]: result.append(f"- {line}")
        elif tag == 'insert':
            for line in new_f.body_lines[j1:j2]: result.append(f"+ {line}")
    return result


# ══════════════════════════════════════════════════════════════
#  공개 API — find_changed_functions
# ══════════════════════════════════════════════════════════════
def find_changed_functions(old_code: str, new_code: str) -> List[ChangedFunction]:
    old_func_list = parse_c_functions(old_code)
    new_func_list = parse_c_functions(new_code)
    old_funcs = {f.name: f for f in old_func_list}
    new_funcs  = {f.name: f for f in new_func_list}
    changed: List[ChangedFunction] = []

    old_globals = _extract_global_lines(old_code, old_func_list)
    new_globals = _extract_global_lines(new_code, new_func_list)
    if old_globals != new_globals:
        global_diff = _make_global_diff(old_globals, new_globals)
        if global_diff:
            changed.append(ChangedFunction(name="__global__", diff_lines=global_diff))

    all_names = list(dict.fromkeys(list(old_funcs.keys()) + list(new_funcs.keys())))
    for name in all_names:
        old_f = old_funcs.get(name)
        new_f = new_funcs.get(name)
        if old_f and new_f:
            if old_f.full_text == new_f.full_text:
                continue
            changed.append(ChangedFunction(name=name,
                           diff_lines=_make_function_diff(old_f, new_f)))
        elif old_f and not new_f:
            lines = [f"  ── 삭제된 함수: {name} ──"]
            for l in old_f.body_lines: lines.append(f"- {l}")
            changed.append(ChangedFunction(name=name, diff_lines=lines))
        elif new_f and not old_f:
            lines = [f"  ── 추가된 함수: {name} ──"]
            for l in new_f.body_lines: lines.append(f"+ {l}")
            changed.append(ChangedFunction(name=name, diff_lines=lines))
    return changed