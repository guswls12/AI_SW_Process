# SEI CERT C Coding Standard (2016) — 규칙 목록 요약

> **출처**: SEI CERT C Coding Standard, 2016 Edition  
> **목적**: C 언어 안전·신뢰·보안 코드 개발을 위한 규칙 모음  
> **총 규칙 수**: 99개

---

## 2. 전처리기 (Preprocessor, PRE)

| 번호 | 규칙 ID | 영문 제목 | 한국어 설명 |
|------|---------|-----------|-------------|
| 2.1 | PRE30-C | Do not create a universal character name through concatenation | 연결(concatenation)을 통해 보편적 문자 이름(UCN)을 생성하지 말 것 |
| 2.2 | PRE31-C | Avoid side effects in arguments to unsafe macros | 안전하지 않은 매크로 인자에 부수 효과(side effect)를 사용하지 말 것 |
| 2.3 | PRE32-C | Do not use preprocessor directives in invocations of function-like macros | 함수형 매크로 호출 시 전처리기 지시문을 사용하지 말 것 |

---

## 3. 선언 및 초기화 (Declarations and Initialization, DCL)

| 번호 | 규칙 ID | 영문 제목 | 한국어 설명 |
|------|---------|-----------|-------------|
| 3.1 | DCL30-C | Declare objects with appropriate storage durations | 적절한 저장 기간을 지정하여 객체를 선언할 것 |
| 3.2 | DCL31-C | Declare identifiers before using them | 식별자는 사용하기 전에 선언할 것 |
| 3.3 | DCL36-C | Do not declare an identifier with conflicting linkage classifications | 충돌하는 링크 분류로 식별자를 선언하지 말 것 |
| 3.4 | DCL37-C | Do not declare or define a reserved identifier | 예약된 식별자를 선언하거나 정의하지 말 것 |
| 3.5 | DCL38-C | Use the correct syntax when declaring a flexible array member | 유연 배열 멤버 선언 시 올바른 문법을 사용할 것 |
| 3.6 | DCL39-C | Avoid information leakage when passing a structure across a trust boundary | 신뢰 경계를 넘어 구조체를 전달할 때 정보 유출을 방지할 것 |
| 3.7 | DCL40-C | Do not create incompatible declarations of the same function or object | 동일한 함수나 객체에 대해 호환되지 않는 선언을 만들지 말 것 |
| 3.8 | DCL41-C | Do not declare variables inside a switch statement before the first case label | switch 문에서 첫 번째 case 레이블 이전에 변수를 선언하지 말 것 |

---

## 4. 표현식 (Expressions, EXP)

| 번호 | 규칙 ID | 영문 제목 | 한국어 설명 |
|------|---------|-----------|-------------|
| 4.1 | EXP30-C | Do not depend on the order of evaluation for side effects | 부수 효과의 평가 순서에 의존하지 말 것 |
| 4.2 | EXP32-C | Do not access a volatile object through a nonvolatile reference | 비휘발성 참조를 통해 volatile 객체에 접근하지 말 것 |
| 4.3 | EXP33-C | Do not read uninitialized memory | 초기화되지 않은 메모리를 읽지 말 것 |
| 4.4 | EXP34-C | Do not dereference null pointers | 널 포인터를 역참조하지 말 것 |
| 4.5 | EXP35-C | Do not modify objects with temporary lifetime | 임시 수명을 가진 객체를 수정하지 말 것 |
| 4.6 | EXP36-C | Do not cast pointers into more strictly aligned pointer types | 더 엄격한 정렬을 요구하는 포인터 타입으로 캐스팅하지 말 것 |
| 4.7 | EXP37-C | Call functions with the correct number and type of arguments | 올바른 수와 타입의 인자로 함수를 호출할 것 |
| 4.8 | EXP39-C | Do not access a variable through a pointer of an incompatible type | 호환되지 않는 타입의 포인터를 통해 변수에 접근하지 말 것 |
| 4.9 | EXP40-C | Do not modify constant objects | 상수 객체를 수정하지 말 것 |
| 4.10 | EXP42-C | Do not compare padding data | 패딩 데이터를 비교하지 말 것 |
| 4.11 | EXP43-C | Avoid undefined behavior when using restrict-qualified pointers | restrict 한정 포인터 사용 시 미정의 동작을 피할 것 |
| 4.12 | EXP44-C | Do not rely on side effects in operands to sizeof, _Alignof, or _Generic | sizeof, _Alignof, _Generic 피연산자의 부수 효과에 의존하지 말 것 |
| 4.13 | EXP45-C | Do not perform assignments in selection statements | 선택문(if/switch) 안에서 대입 연산을 수행하지 말 것 |
| 4.14 | EXP46-C | Do not use a bitwise operator with a Boolean-like operand | 불리언 유사 피연산자에 비트 연산자를 사용하지 말 것 |

---

## 5. 정수 (Integers, INT)

| 번호 | 규칙 ID | 영문 제목 | 한국어 설명 |
|------|---------|-----------|-------------|
| 5.1 | INT30-C | Ensure that unsigned integer operations do not wrap | 부호 없는 정수 연산에서 래핑(wrap)이 발생하지 않도록 보장할 것 |
| 5.2 | INT31-C | Ensure that integer conversions do not result in lost or misinterpreted data | 정수 변환 시 데이터 손실이나 오해석이 발생하지 않도록 보장할 것 |
| 5.3 | INT32-C | Ensure that operations on signed integers do not result in overflow | 부호 있는 정수 연산에서 오버플로우가 발생하지 않도록 보장할 것 |
| 5.4 | INT33-C | Ensure that division and remainder operations do not result in divide-by-zero errors | 나눗셈 및 나머지 연산에서 0으로 나누기 오류가 발생하지 않도록 보장할 것 |
| 5.5 | INT34-C | Do not shift an expression by a negative number of bits or by greater than or equal to the number of bits that exist in the operand | 음수 비트 수 또는 피연산자 비트 수 이상으로 시프트하지 말 것 |
| 5.6 | INT35-C | Use correct integer precisions | 올바른 정수 정밀도를 사용할 것 |
| 5.7 | INT36-C | Converting a pointer to integer or integer to pointer | 포인터를 정수로 또는 정수를 포인터로 변환할 때 주의할 것 |

---

## 6. 부동소수점 (Floating Point, FLP)

| 번호 | 규칙 ID | 영문 제목 | 한국어 설명 |
|------|---------|-----------|-------------|
| 6.1 | FLP30-C | Do not use floating-point variables as loop counters | 부동소수점 변수를 루프 카운터로 사용하지 말 것 |
| 6.2 | FLP32-C | Prevent or detect domain and range errors in math functions | 수학 함수에서 도메인 및 범위 오류를 방지하거나 감지할 것 |
| 6.3 | FLP34-C | Ensure that floating-point conversions are within range of the new type | 부동소수점 변환 시 새 타입의 범위 내에 있음을 보장할 것 |
| 6.4 | FLP36-C | Preserve precision when converting integral values to floating-point type | 정수 값을 부동소수점 타입으로 변환할 때 정밀도를 유지할 것 |
| 6.5 | FLP37-C | Do not use object representations to compare floating-point values | 객체 표현(비트 패턴)을 이용하여 부동소수점 값을 비교하지 말 것 |

---

## 7. 배열 (Array, ARR)

| 번호 | 규칙 ID | 영문 제목 | 한국어 설명 |
|------|---------|-----------|-------------|
| 7.1 | ARR30-C | Do not form or use out-of-bounds pointers or array subscripts | 범위를 벗어난 포인터나 배열 인덱스를 생성하거나 사용하지 말 것 |
| 7.2 | ARR32-C | Ensure size arguments for variable length arrays are in a valid range | 가변 길이 배열의 크기 인자가 유효한 범위 내에 있음을 보장할 것 |
| 7.3 | ARR36-C | Do not subtract or compare two pointers that do not refer to the same array | 동일한 배열을 참조하지 않는 두 포인터를 빼거나 비교하지 말 것 |
| 7.4 | ARR37-C | Do not add or subtract an integer to a pointer to a non-array object | 배열이 아닌 객체에 대한 포인터에 정수를 더하거나 빼지 말 것 |
| 7.5 | ARR38-C | Guarantee that library functions do not form invalid pointers | 라이브러리 함수가 유효하지 않은 포인터를 형성하지 않도록 보장할 것 |
| 7.6 | ARR39-C | Do not add or subtract a scaled integer to a pointer | 포인터에 스케일된 정수를 더하거나 빼지 말 것 |

---

## 8. 문자 및 문자열 (Characters and Strings, STR)

| 번호 | 규칙 ID | 영문 제목 | 한국어 설명 |
|------|---------|-----------|-------------|
| 8.1 | STR30-C | Do not attempt to modify string literals | 문자열 리터럴을 수정하려 하지 말 것 |
| 8.2 | STR31-C | Guarantee that storage for strings has sufficient space for character data and the null terminator | 문자열 저장 공간이 문자 데이터와 널 종결자를 위한 충분한 공간을 가지도록 보장할 것 |
| 8.3 | STR32-C | Do not pass a non-null-terminated character sequence to a library function that expects a string | 문자열을 기대하는 라이브러리 함수에 널 종결되지 않은 문자 시퀀스를 전달하지 말 것 |
| 8.4 | STR34-C | Cast characters to unsigned char before converting to larger integer sizes | 더 큰 정수 크기로 변환하기 전에 문자를 unsigned char로 캐스팅할 것 |
| 8.5 | STR37-C | Arguments to character-handling functions must be representable as an unsigned char | 문자 처리 함수의 인자는 unsigned char로 표현 가능해야 할 것 |
| 8.6 | STR38-C | Do not confuse narrow and wide character strings and functions | 좁은 문자(narrow)와 넓은 문자(wide) 문자열 및 함수를 혼동하지 말 것 |

---

## 9. 메모리 관리 (Memory Management, MEM)

| 번호 | 규칙 ID | 영문 제목 | 한국어 설명 |
|------|---------|-----------|-------------|
| 9.1 | MEM30-C | Do not access freed memory | 해제된 메모리에 접근하지 말 것 |
| 9.2 | MEM31-C | Free dynamically allocated memory when no longer needed | 더 이상 필요 없는 동적 할당 메모리는 해제할 것 |
| 9.3 | MEM33-C | Allocate and copy structures containing a flexible array member dynamically | 유연 배열 멤버를 포함하는 구조체는 동적으로 할당하고 복사할 것 |
| 9.4 | MEM34-C | Only free memory allocated dynamically | 동적으로 할당된 메모리만 해제할 것 |
| 9.5 | MEM35-C | Allocate sufficient memory for an object | 객체에 충분한 메모리를 할당할 것 |
| 9.6 | MEM36-C | Do not modify the alignment of objects by calling realloc() | realloc() 호출로 객체의 정렬을 변경하지 말 것 |

---

## 10. 입출력 (Input/Output, FIO)

| 번호 | 규칙 ID | 영문 제목 | 한국어 설명 |
|------|---------|-----------|-------------|
| 10.1 | FIO30-C | Exclude user input from format strings | 사용자 입력을 포맷 문자열에 포함하지 말 것 |
| 10.2 | FIO32-C | Do not perform operations on devices that are only appropriate for files | 파일에만 적합한 작업을 디바이스에 수행하지 말 것 |
| 10.3 | FIO34-C | Distinguish between characters read from a file and EOF or WEOF | 파일에서 읽은 문자와 EOF/WEOF를 구별할 것 |
| 10.4 | FIO37-C | Do not assume that fgets() or fgetws() returns a nonempty string when successful | 성공 시 fgets() 또는 fgetws()가 비어 있지 않은 문자열을 반환한다고 가정하지 말 것 |
| 10.5 | FIO38-C | Do not copy a FILE object | FILE 객체를 복사하지 말 것 |
| 10.6 | FIO39-C | Do not alternately input and output from a stream without an intervening flush or positioning call | 중간에 플러시나 위치 지정 호출 없이 스트림에서 입출력을 번갈아 하지 말 것 |
| 10.7 | FIO40-C | Reset strings on fgets() or fgetws() failure | fgets() 또는 fgetws() 실패 시 문자열을 초기화할 것 |
| 10.8 | FIO41-C | Do not call getc(), putc(), getwc(), or putwc() with a stream argument that has side effects | 부수 효과가 있는 스트림 인자로 getc(), putc(), getwc(), putwc()를 호출하지 말 것 |
| 10.9 | FIO42-C | Close files when they are no longer needed | 더 이상 필요 없는 파일은 닫을 것 |
| 10.10 | FIO44-C | Only use values for fsetpos() that are returned from fgetpos() | fsetpos()에는 fgetpos()에서 반환된 값만 사용할 것 |
| 10.11 | FIO45-C | Avoid TOCTOU race conditions while accessing files | 파일 접근 시 TOCTOU(검사-사용 시점 불일치) 경쟁 조건을 피할 것 |
| 10.12 | FIO46-C | Do not access a closed file | 닫힌 파일에 접근하지 말 것 |
| 10.13 | FIO47-C | Use valid format strings | 유효한 포맷 문자열을 사용할 것 |

---

## 11. 환경 (Environment, ENV)

| 번호 | 규칙 ID | 영문 제목 | 한국어 설명 |
|------|---------|-----------|-------------|
| 11.1 | ENV30-C | Do not modify the object referenced by the return value of certain functions | 특정 함수의 반환값이 참조하는 객체를 수정하지 말 것 |
| 11.2 | ENV31-C | Do not rely on an environment pointer following an operation that may invalidate it | 무효화될 수 있는 작업 이후에 환경 포인터에 의존하지 말 것 |
| 11.3 | ENV32-C | All exit handlers must return normally | 모든 종료 핸들러는 정상적으로 반환해야 할 것 |
| 11.4 | ENV33-C | Do not call system() | system() 함수를 호출하지 말 것 |
| 11.5 | ENV34-C | Do not store pointers returned by certain functions | 특정 함수가 반환한 포인터를 저장하지 말 것 |

---

## 12. 시그널 (Signals, SIG)

| 번호 | 규칙 ID | 영문 제목 | 한국어 설명 |
|------|---------|-----------|-------------|
| 12.1 | SIG30-C | Call only asynchronous-safe functions within signal handlers | 시그널 핸들러 내에서는 비동기 안전 함수만 호출할 것 |
| 12.2 | SIG31-C | Do not access shared objects in signal handlers | 시그널 핸들러에서 공유 객체에 접근하지 말 것 |
| 12.3 | SIG34-C | Do not call signal() from within interruptible signal handlers | 인터럽트 가능한 시그널 핸들러 내에서 signal()을 호출하지 말 것 |
| 12.4 | SIG35-C | Do not return from a computational exception signal handler | 연산 예외 시그널 핸들러에서 반환하지 말 것 |

---

## 13. 오류 처리 (Error Handling, ERR)

| 번호 | 규칙 ID | 영문 제목 | 한국어 설명 |
|------|---------|-----------|-------------|
| 13.1 | ERR30-C | Set errno to zero before calling a library function known to set errno, and check errno only after the function returns a value indicating failure | errno를 설정하는 것으로 알려진 라이브러리 함수 호출 전 errno를 0으로 설정하고, 함수가 실패를 나타내는 값을 반환한 후에만 errno를 확인할 것 |
| 13.2 | ERR32-C | Do not rely on indeterminate values of errno | errno의 불확정 값에 의존하지 말 것 |
| 13.3 | ERR33-C | Detect and handle standard library errors | 표준 라이브러리 오류를 감지하고 처리할 것 |

---

## 14. 동시성 (Concurrency, CON)

| 번호 | 규칙 ID | 영문 제목 | 한국어 설명 |
|------|---------|-----------|-------------|
| 14.1 | CON30-C | Clean up thread-specific storage | 스레드별 저장소를 정리할 것 |
| 14.2 | CON31-C | Do not destroy a mutex while it is locked | 잠긴 상태의 뮤텍스를 소멸시키지 말 것 |
| 14.3 | CON32-C | Prevent data races when accessing bit-fields from multiple threads | 여러 스레드에서 비트 필드에 접근할 때 데이터 경쟁을 방지할 것 |
| 14.4 | CON33-C | Avoid race conditions when using library functions | 라이브러리 함수 사용 시 경쟁 조건을 피할 것 |
| 14.5 | CON34-C | Declare objects shared between threads with appropriate storage durations | 스레드 간 공유 객체를 적절한 저장 기간으로 선언할 것 |
| 14.6 | CON35-C | Avoid deadlock by locking in a predefined order | 미리 정의된 순서로 잠금을 획득하여 교착 상태(deadlock)를 피할 것 |
| 14.7 | CON36-C | Wrap functions that can spuriously wake up in a loop | 허위 깨어남(spurious wakeup)이 발생할 수 있는 함수를 루프로 감쌀 것 |
| 14.8 | CON37-C | Do not call signal() in a multithreaded program | 멀티스레드 프로그램에서 signal()을 호출하지 말 것 |
| 14.9 | CON38-C | Preserve thread safety and liveness when using condition variables | 조건 변수 사용 시 스레드 안전성과 활성(liveness)을 유지할 것 |
| 14.10 | CON39-C | Do not join or detach a thread that was previously joined or detached | 이미 join 또는 detach된 스레드를 다시 join/detach하지 말 것 |
| 14.11 | CON40-C | Do not refer to an atomic variable twice in an expression | 하나의 표현식에서 원자 변수를 두 번 참조하지 말 것 |
| 14.12 | CON41-C | Wrap functions that can fail spuriously in a loop | 허위 실패(spurious failure)가 발생할 수 있는 함수를 루프로 감쌀 것 |

---

## 15. 기타 (Miscellaneous, MSC)

| 번호 | 규칙 ID | 영문 제목 | 한국어 설명 |
|------|---------|-----------|-------------|
| 15.1 | MSC30-C | Do not use the rand() function for generating pseudorandom numbers | 의사 난수 생성에 rand() 함수를 사용하지 말 것 |
| 15.2 | MSC32-C | Properly seed pseudorandom number generators | 의사 난수 생성기를 적절히 시드(seed)할 것 |
| 15.3 | MSC33-C | Do not pass invalid data to the asctime() function | asctime() 함수에 유효하지 않은 데이터를 전달하지 말 것 |
| 15.4 | MSC37-C | Ensure that control never reaches the end of a non-void function | void가 아닌 함수의 끝에 제어 흐름이 도달하지 않도록 보장할 것 |
| 15.5 | MSC38-C | Do not treat a predefined identifier as an object if it might only be implemented as a macro | 매크로로만 구현될 수 있는 미리 정의된 식별자를 객체처럼 취급하지 말 것 |
| 15.6 | MSC39-C | Do not call va_arg() on a va_list that has an indeterminate value | 불확정 값을 가진 va_list에 va_arg()를 호출하지 말 것 |
| 15.7 | MSC40-C | Do not violate constraints | 제약 조건을 위반하지 말 것 |

---

## 대분류 요약

| 챕터 | 접두사 | 분야 | 규칙 수 |
|------|--------|------|---------|
| 2 | PRE | 전처리기 (Preprocessor) | 3 |
| 3 | DCL | 선언 및 초기화 (Declarations and Initialization) | 8 |
| 4 | EXP | 표현식 (Expressions) | 14 |
| 5 | INT | 정수 (Integers) | 7 |
| 6 | FLP | 부동소수점 (Floating Point) | 5 |
| 7 | ARR | 배열 (Array) | 6 |
| 8 | STR | 문자 및 문자열 (Characters and Strings) | 6 |
| 9 | MEM | 메모리 관리 (Memory Management) | 6 |
| 10 | FIO | 입출력 (Input/Output) | 13 |
| 11 | ENV | 환경 (Environment) | 5 |
| 12 | SIG | 시그널 (Signals) | 4 |
| 13 | ERR | 오류 처리 (Error Handling) | 3 |
| 14 | CON | 동시성 (Concurrency) | 12 |
| 15 | MSC | 기타 (Miscellaneous) | 7 |
| **합계** | | | **99** |
