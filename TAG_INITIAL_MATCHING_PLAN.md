# 태그 앞글자/초성 매칭 자동완성 실행 계획서

## 1. 목표

Tag Batch 창과 Rule34 설정 창의 태그 입력에서 사용자가 태그 전체를 입력하지 않아도 추천 태그를 찾을 수 있게 만든다.

지원할 검색 방식은 다음과 같다.

- 일반 포함 검색: `hair` -> `black_hair`, `long_hair`
- 일반 prefix 검색: `bla` -> `black_hair`
- 단어 앞글자 검색: `bh` -> `black_hair`, `blue_hair`
- underscore/공백 단어 검색: `le` -> `long_ears`
- 한글 초성 검색: `ㄴㅇ` -> `니어_오토마타`
- 혼합 입력 검색: 영어 태그, artist 태그, character 태그, 한글 별칭을 같은 검색 엔진에서 처리

현재 booru 태그는 대부분 영어/underscore 기반이므로 1차 구현에서는 `black_hair -> bh` 같은 단어 앞글자 매칭이 가장 중요하다. 한글 초성 매칭은 Known.txt, characters.db, 사용자가 직접 넣은 한글 별칭까지 확장할 수 있도록 같이 설계한다.

## 2. 현재 코드 조사 결과

### 2.1 기존 자동완성 위치

현재 자동완성은 `src/ui/dialogs/Rule34SettingsDialog.py`에만 있다.

- `MultiCompleter`
  - comma-separated 입력을 지원한다.
  - `splitPath()`에서 마지막 comma 뒤 텍스트만 검색어로 사용한다.
  - `Ctrl + Down`으로 추천 항목을 빠르게 확정하는 특수 동작이 있다.
- `setup_autocomplete()`
  - `appdata/characters.db`의 `Characters.raw_string`을 모두 읽어 `self.all_tags_cache`에 저장한다.
- `update_completer_model()`
  - 현재는 `search_text in tag.lower()` 방식의 단순 포함 검색이다.
  - 결과 정렬은 exact/prefix/contains에 가까운 우선순위를 직접 계산한다.

### 2.2 새 Tag Batch 창 상태

현재 `src/ui/dialogs/TagBatchDownloadDialog.py`에는 다음 입력창이 있다.

- Positive
- Negative
- Artist
- Character
- General

아직 `QCompleter`가 붙어 있지 않다. 따라서 앞글자/초성 매칭은 Tag Batch 창에 새로 붙이는 동시에, 기존 Rule34 설정 창의 자동완성도 같은 로직을 쓰도록 정리할 수 있다.

### 2.3 현재 데이터 출처

확인된 로컬 태그 데이터 출처는 다음이다.

- `appdata/characters.db`
  - Rule34 설정 창에서 다운로드 가능한 오프라인 DB
  - 테이블: `Characters`
  - 주요 컬럼: `raw_string`, `character_name`, `is_favorite`
- `appdata/Known.txt`
  - 현재는 비어 있을 수 있음
  - 사용자 정의 캐릭터/시리즈 이름 저장소
- 다운로드 후 DB
  - `src/core/database_manager.py`에서 `Tags`, `ImageTags`, `MangaTags` 테이블을 관리한다.
  - 이미 받은 파일의 태그를 향후 추천 데이터로 재사용할 수 있다.

## 3. 핵심 설계

### 3.1 공통 매칭 모듈 추가

새 파일 후보:

```text
src/core/tag_matcher.py
```

역할:

- 태그 정규화
- 영어 단어 앞글자 key 생성
- 한글 초성 key 생성
- 검색어와 태그의 match score 계산
- 추천 결과 정렬

예상 함수:

```python
def normalize_search_text(text: str) -> str:
    ...

def split_tag_words(tag: str) -> list[str]:
    ...

def build_acronym(tag: str) -> str:
    ...

def build_hangul_initials(text: str) -> str:
    ...

def score_tag_match(query: str, tag: str) -> int | None:
    ...

def find_tag_matches(query: str, tags: list[str], limit: int = 40) -> list[str]:
    ...
```

### 3.2 영어 앞글자 매칭 규칙

태그를 `_`, 공백, `-`, `:`, 괄호 기준으로 단어 분리한다.

예시:

```text
black_hair        -> words: black, hair       -> acronym: bh
blue_eyes         -> words: blue, eyes        -> acronym: be
artist:name_here  -> words: artist, name, here -> acronym: anh
nier_automata     -> words: nier, automata    -> acronym: na
```

검색 규칙:

- `bh` 입력 시 `black_hair`, `brown_hair`, `blue_hair`를 추천한다.
- `b h` 또는 `b_h` 입력도 `bh`로 정규화해서 같은 결과를 낸다.
- `blh`처럼 조금 더 긴 acronym은 `black_hair`보다 `black_long_hair` 같은 태그를 우선한다.

### 3.3 한글 초성 매칭 규칙

한글 음절은 유니코드 분해 공식을 사용한다.

```text
가-힣 범위의 코드포인트
초성 index = (ord(char) - ord("가")) // 588
```

초성 배열:

```text
ㄱ ㄲ ㄴ ㄷ ㄸ ㄹ ㅁ ㅂ ㅃ ㅅ ㅆ ㅇ ㅈ ㅉ ㅊ ㅋ ㅌ ㅍ ㅎ
```

예시:

```text
니어_오토마타 -> ㄴㅇㅇㅌㅁㅌ
블루_아카이브 -> ㅂㄹㅇㅋㅇㅂ
```

검색 규칙:

- 사용자가 `ㄴㅇ`을 입력하면 `니어_오토마타`를 추천한다.
- 사용자가 `ㅂㄹ`을 입력하면 `블루_아카이브`를 추천한다.
- 태그가 영어라면 한글 초성 key는 비어 있어도 된다.

### 3.4 점수/정렬 규칙

추천 품질을 위해 match score를 단계화한다. 낮은 점수가 더 우선이다.

1. 완전 일치: `black_hair` == `black_hair`
2. prefix 일치: `black` -> `black_hair`
3. 단어 prefix 일치: `hair` -> `black_hair`
4. acronym prefix 일치: `bh` -> `black_hair`
5. 한글 초성 prefix 일치: `ㄴㅇ` -> `니어_오토마타`
6. contains 일치: `ack` -> `black_hair`
7. acronym contains 일치
8. 초성 contains 일치

동점 정렬:

- favorite 태그 우선, 가능하면 `characters.db.is_favorite`
- 짧은 태그 우선
- 알파벳순

## 4. UI 통합 계획

### 4.1 공통 Completer 클래스 분리

현재 `Rule34SettingsDialog.py` 안에 있는 `MultiCompleter`는 재사용하기 어렵다. 새 공통 UI 파일을 만든다.

파일 후보:

```text
src/ui/widgets/tag_completer.py
```

내용:

- `MultiCompleter`
- comma-separated 입력 처리
- 현재 token 추출
- 선택한 추천 태그를 마지막 token에 삽입
- `Ctrl + Down` 확정 기능 유지

이렇게 하면 Rule34 설정 창과 Tag Batch 창이 같은 completer를 쓸 수 있다.

### 4.2 Tag Batch 창에 자동완성 연결

`TagBatchDownloadDialog`의 다섯 입력창에 completer를 붙인다.

- Positive: 전체 태그 후보
- Negative: 전체 태그 후보, 삽입 시 `-`는 붙이지 않음
  - 현재 URL 생성 단계에서 negative는 자동으로 `-tag`가 된다.
- Artist: artist 후보를 우선 표시
- Character: character 후보를 우선 표시
- General: general 후보를 우선 표시

1차 구현에서는 category별 데이터가 충분하지 않을 수 있으므로, 모든 입력창에 같은 후보 목록을 붙이고, 이후 tag provider가 category 정보를 주면 분리한다.

### 4.3 Rule34 설정 창 자동완성 교체

기존:

```python
raw_matches = [tag for tag in self.all_tags_cache if search_text in tag.lower()]
```

변경:

```python
raw_matches = find_tag_matches(search_text, self.all_tags_cache, limit=40)
```

기존 `MultiCompleter`의 comma 처리와 `Ctrl + Down` 동작은 유지하되, 필터링과 정렬만 새 엔진으로 교체한다.

## 5. 데이터 로딩 계획

### 5.1 1차 데이터

1차는 네트워크 없이 가능한 로컬 데이터만 사용한다.

- `appdata/characters.db`의 `Characters.raw_string`
- `Known.txt`
- 기존 다운로드 DB의 `Tags.tag_name`, 가능하면 사용

장점:

- API 호출 없음
- UI freeze 위험 낮음
- 기존 Rule34 설정의 오프라인 DB와 잘 맞음

### 5.2 2차 데이터

계획서의 다음 단계에서 `tag_search_client.py`를 만들면 다음 API 결과도 자동완성 후보로 합친다.

- Danbooru tags API
- Gelbooru tag API
- Rule34 tag API
- Rule34Video는 검색/태그 API 구조 확인 후 별도 provider

이 단계에서는 캐시 DB가 필요하다.

파일 후보:

```text
appdata/tag_cache.db
```

테이블 후보:

```sql
TagSuggestion(
    source TEXT,
    name TEXT,
    category TEXT,
    post_count INTEGER,
    updated_at TEXT,
    PRIMARY KEY(source, name)
)
```

## 6. 구현 단계

### 1단계: 매칭 엔진

추가:

- `src/core/tag_matcher.py`

구현:

- 영어/underscore 단어 분리
- acronym 생성
- 한글 초성 생성
- score 기반 추천 정렬

검증:

- `black_hair`가 `bh`로 검색되는지
- `blue_eyes`가 `be`로 검색되는지
- `니어_오토마타`가 `ㄴㅇ`로 검색되는지
- contains 검색이 기존보다 나빠지지 않는지

### 2단계: 공통 completer 위젯

추가:

- `src/ui/widgets/tag_completer.py`

구현:

- 기존 `MultiCompleter` 기능 이동 또는 복사 후 정리
- comma-separated token 자동완성 지원
- 검색 타이머 debounce 지원
- `find_tag_matches()` 호출

### 3단계: Tag Batch 창 연결

수정:

- `src/ui/dialogs/TagBatchDownloadDialog.py`

구현:

- 다섯 태그 입력창에 completer 적용
- `characters.db`, `Known.txt`, 다운로드 DB 태그를 후보로 로딩
- 후보가 없을 때는 조용히 비활성화

### 4단계: Rule34 설정 창 기존 자동완성 교체

수정:

- `src/ui/dialogs/Rule34SettingsDialog.py`

구현:

- 기존 `update_completer_model()`의 contains 필터를 공통 matcher로 교체
- 기존 `Ctrl + Down` 동작 유지
- 기존 `characters.db` 다운로드 후 자동완성 reload 동작 유지

### 5단계: 성능 최적화

태그 후보가 많아지면 매번 모든 태그에 대해 초성/acronym을 다시 계산하면 느릴 수 있다.

대응:

- `TagSearchIndex` 클래스 도입
- 태그 로딩 시 미리 다음 값을 계산
  - normalized
  - display
  - words
  - acronym
  - hangul_initials
- 입력마다 score만 계산

후보가 10만 개 이상일 때도 입력 지연이 300ms 이하가 되도록 한다.

## 7. 테스트 계획

현재 프로젝트에는 별도 테스트 폴더가 없다. 따라서 1차로는 작은 단위 테스트 스크립트 또는 `py_compile` + 직접 함수 검증을 사용한다.

필수 검증 케이스:

```text
query: bh
tags: black_hair, blue_hair, blonde_hair, long_hair
expected: black_hair/blue_hair/blonde_hair가 long_hair보다 우선

query: be
tags: blue_eyes, brown_eyes, black_hair
expected: blue_eyes, brown_eyes 우선

query: ㄴㅇ
tags: 니어_오토마타, 블루_아카이브
expected: 니어_오토마타

query: automata
tags: nier_automata
expected: nier_automata

query: artist_name
tags: artist:name, artist_name
expected: 정확도가 높은 항목 우선
```

UI 검증:

- Tag Batch 창에서 `bh` 입력 시 추천 목록 표시
- comma 뒤에서 `so, bh` 입력 시 마지막 token만 자동완성
- 추천 선택 시 기존 입력 `so, `가 유지되고 선택 태그만 뒤에 붙음
- Rule34 설정 창의 기존 자동완성이 깨지지 않음

## 8. 위험 요소와 대응

### 8.1 너무 많은 후보로 UI 지연

문제:

- `characters.db`가 크면 매 키 입력마다 리스트 전체를 순회할 수 있다.

대응:

- 300ms debounce 유지
- 후보 index 사전 계산
- 결과 limit 40 유지

### 8.2 영문 acronym 오탐

문제:

- `bh`가 너무 많은 태그와 매칭될 수 있다.

대응:

- acronym은 query 길이 2 이상일 때만 활성화
- exact/prefix/word-prefix를 acronym보다 우선한다.

### 8.3 한글 초성 입력 판별

문제:

- 사용자가 `ㄱㄴ`처럼 자모만 입력한 경우와 일반 문자를 섞어 입력한 경우가 있다.

대응:

- query에 초성 문자가 포함되면 초성 key 검색 활성화
- 일반 한글 단어 입력은 normalized contains/prefix도 같이 검색

### 8.4 사이트별 태그 category 부족

문제:

- Artist/Character/General 입력창을 분리했지만, 현재 로컬 DB가 category를 충분히 제공하지 않을 수 있다.

대응:

- 1차는 모든 후보를 보여준다.
- 2차 tag provider에서 category가 들어오면 category별 우선순위만 추가한다.

## 9. 추천 구현 순서

가장 안전한 순서는 다음이다.

1. `tag_matcher.py`만 먼저 추가하고 함수 검증
2. Tag Batch 창에만 새 자동완성 연결
3. 사용성이 괜찮으면 Rule34 설정 창 자동완성도 같은 matcher로 교체
4. 이후 Danbooru/Gelbooru/Rule34 API tag provider와 캐시 DB 추가

이 순서가 좋은 이유는 기존 Rule34 설정 창의 자동완성을 바로 대대적으로 바꾸면 기존 사용 흐름이 깨질 수 있기 때문이다. Tag Batch 창은 새 기능이라 먼저 실험하기 좋고, matcher가 안정되면 기존 창까지 확장하면 된다.

## 10. 완료 기준

1차 완료 기준:

- Tag Batch 창에서 `bh` 입력 시 `black_hair`, `blue_hair` 같은 단어 앞글자 태그가 추천된다.
- 한글 후보가 있을 경우 `ㄴㅇ` 같은 초성 입력으로 추천된다.
- comma-separated 입력에서 마지막 태그만 자동완성된다.
- 자동완성 후보가 없어도 입력/다운로드 흐름은 깨지지 않는다.
- `py_compile` 검증을 통과한다.

2차 완료 기준:

- Rule34 설정 창의 기존 자동완성이 새 matcher를 사용한다.
- `characters.db` 다운로드 후 자동완성 reload가 그대로 작동한다.
- Tag Batch의 Artist/Character/General 필드가 category 우선순위를 반영한다.

