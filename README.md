# STE-KO 스킬

AI 에이전트가 한국어 업무 글을 읽기 쉽게 쓰도록 하는 스킬입니다. Claude Code에서 씁니다.

기술 문서, 커밋 메시지, PR 본문, 장애 보고, Slack·Notion 업무 글, UI 문구에 적용합니다. 규칙은 한국어 통제 언어 규격 [STE-KO](https://github.com/beamonic/ste-ko)를 기반으로 합니다. STE-KO는 항공 정비 매뉴얼 규격 ASD-STE100의 방식을 한국어에 맞게 새로 쓴 규격입니다.

## 무엇이 달라지나

> 고치기 전: 금일 오후 배포 관련하여 이슈가 발생되어 확인해 본 결과, 결제 모듈 토큰 갱신 처리 로직 부분에서 문제가 있는 것으로 보여지며, 조만간 안정화 작업이 진행될 예정입니다.

> 고친 후: 10월 12일 14시 배포 뒤 결제가 실패하고 있습니다. 결제 모듈이 만료된 토큰을 갱신하지 않는 것으로 보입니다(추론, 실패 로그 42건이 모두 `TokenExpired`). 수정 일정은 [담당자 확인 필요]입니다.

- 결론과 현재 상태를 먼저 씁니다.
- 이중피동(`보여지며`), 명사 나열(`토큰 갱신 처리 로직 부분`), 모호한 말(`이슈`, `조만간`)을 걷어냅니다.
- 확인한 사실과 추론을 나눕니다.
- 입력에 없는 일정은 만들지 않고 자리만 표시합니다.

## 설치

Claude Code 사용자 스킬 폴더에 받습니다.

```bash
git clone https://github.com/junwonkim07/ste-ko-skill ~/.claude/skills/ste-ko
```

새 세션부터 스킬 목록에 `ste-ko`가 보입니다. 업데이트는 `git pull`로 받습니다.

```bash
git -C ~/.claude/skills/ste-ko pull
```

프로젝트 하나에만 쓰려면 그 저장소의 `.claude/skills/ste-ko`에 받습니다.

## 쓰는 법

따로 부르지 않아도 됩니다. 한국어 문서, 커밋, PR, 보고를 쓰거나 고쳐 달라고 하면 스킬이 적용됩니다.

- "이 장애 보고 읽기 쉽게 고쳐줘"
- "README 번역투 빼줘"
- "이 PR 본문 STE-KO로 다시 써줘"
- "무엇을 고쳤는지 표로 보여줘" (규칙 번호와 전후 비교)

일상 대화 답변에는 적용하지 않습니다. 영어 글은 영어판 [asd-ste100-skill](https://github.com/danyuchn/asd-ste100-skill)을 함께 쓰면 됩니다.

## 검사기

`scripts/ste-ko-lint.py`가 기계로 셀 수 있는 규칙을 검사합니다. 파이썬 표준 라이브러리만 씁니다.

```bash
python3 ~/.claude/skills/ste-ko/scripts/ste-ko-lint.py docs/장애보고.md
python3 ~/.claude/skills/ste-ko/scripts/ste-ko-lint.py 'docs/**/*.md' --all
git log -1 --format=%B | python3 ~/.claude/skills/ste-ko/scripts/ste-ko-lint.py - --surface 코딩
```

```
docs/장애보고.md:3	3.2	hard	이중피동 `보여지며`
docs/장애보고.md:3	1.3	warn	`를 통해` (A절 -을 통하-) → -으로 / -로
docs/장애보고.md:7	8.1	hard	범위에 물결표 `3~5` — 마크다운이 취소선으로 읽는다. `-` 를 쓴다
```

| 등급 | 무엇을 잡나 | 종료 코드 |
|---|---|---|
| `hard` | 이중피동, 범위에 쓴 물결표 | 1 |
| `warn` | 번역투, 공문투, 빈 동사, 명사화, 긴 문장 | 0 (`--strict`면 1) |
| `info` | 모호어, 완충어, 수치 표현 | 0, `--all`로 봅니다 |

`hard`가 있으면 종료 코드 1을 내므로 CI나 커밋 훅에 걸 수 있습니다.

## 원본과 다른 점

### 규칙 적용

원본 STE-KO는 규칙을 엄격하게 강제합니다. 이 스킬은 뜻을 바꾸는 강제를 풀었습니다. 방향은 [Gudals0320/asd-ste100-kor](https://github.com/Gudals0320/asd-ste100-kor)의 판단 기준을 참고했습니다.

| 원본 | 이 스킬 |
|---|---|
| 문장 25어절 상한 `필수` | 다시 읽어 볼 신호로만 씁니다 |
| `-일 수도 있습니다`, `약 30분` 금지 | 확신 수준과 추정치는 그대로 둡니다 |
| `일부`, `대부분` 금지 | 수치를 알 때만 수치로 바꿉니다 |
| 비유 금지 | 설명 글에서는 차이를 밝히고 씁니다 |
| `-하십시오`로 통일 | 사용자와 기존 글의 말투를 따릅니다 |
| 모든 답을 다음 행동으로 끝냄 | 실행이나 결정이 필요한 글에만 씁니다 |
| 매 응답에 적용 (플러그인 출력 스타일) | 남이 읽을 글에만 적용합니다 |

### 검사기

원본 검사기(`scripts/lint.py`)는 사전에 있는 표현 상당수를 잡지 못했습니다. 같은 문장을 두 검사기로 돌린 결과입니다.

| 문장 | 원본 | 이 스킬 |
|---|---|---|
| 이 문제에 대해 설명한다. | 못 잡음 | `에 대해` (A절) |
| 이를 통해 해결했다. | 못 잡음 | `를 통해` (A절) |
| 장애로 인해 늦어졌다. | 못 잡음 | `로 인해` (A절) |
| 고객과 관련된 데이터다. | 못 잡음 | `과 관련된` (A절) |
| 이슈가 있습니다. | 못 잡음 | `이슈가` (E절) |
| 성능이 개선될 것이다. | 못 잡음 | `개선될` (E절) |
| 변경되어졌다. | 못 잡음 | 이중피동 |
| 두 기능을 통합했다. | 잡지 않음 | 잡지 않음 (`-을 통하-`와 구별) |
| 서울에 대학이 있다. | 잡지 않음 | 잡지 않음 (`-에 대하-`와 구별) |

고친 점은 다섯입니다.

1. 앞말에 붙는 항목(`-에 대하-`, `-되어지-`)을 잡습니다. 원본은 앞에 한글이 붙은 경우를 모두 건너뛰었습니다.
2. 조사의 받침 짝을 함께 잡습니다. `-을 통하-`가 `를 통해`도 잡습니다.
3. 명사 항목 뒤에 조사나 `-하다`, `-되다`가 붙어도 잡습니다.
4. 어미가 만드는 받침(ㄴ ㄹ ㅁ ㅂ ㅆ)만 열어서 `통합`, `대학` 같은 오탐을 막습니다.
5. 한 줄에 여러 표현이 있으면 모두 알립니다. 원본은 첫 번째만 알렸습니다.

## 구성

```
SKILL.md                         스킬 본문 (에이전트가 읽는 규칙)
references/judgment.md           느슨하게 적용하는 판단 기준과 전후 예시
references/upstream/SPEC.md      STE-KO 규칙 본문 원문
references/upstream/dictionary.md  비승인 표현 대응표 원문
references/upstream/LICENSE      원문 라이선스 (MIT, Beamonic)
scripts/ste-ko-lint.py           검사기
tests/test_skill.py              검사기와 스킬 파일 테스트
```

테스트는 이렇게 돌립니다.

```bash
python3 -m unittest discover -s tests
```

## 출처와 라이선스

- [beamonic/ste-ko](https://github.com/beamonic/ste-ko) (MIT, Copyright (c) 2026 Beamonic): `references/upstream/`의 SPEC.md와 dictionary.md는 커밋 `fd351fe` 원문 그대로입니다. 검사기는 원본 `scripts/lint.py`를 고쳐 썼습니다.
- [Gudals0320/asd-ste100-kor](https://github.com/Gudals0320/asd-ste100-kor) (MIT): 판단 기준의 방향을 참고했습니다. 문장과 예시는 새로 썼습니다.
- ASD-STE100은 ASD(Aerospace, Security and Defence Industries Association of Europe)의 저작물입니다. 이 저장소에는 ASD-STE100 원문과 사전이 없습니다. 공식 번역이나 인증된 구현이 아닙니다.

이 저장소는 [MIT 라이선스](LICENSE)를 따릅니다. 원본 고지는 [NOTICE.md](NOTICE.md)에 있습니다.
