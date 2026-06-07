# 태그 기반 일괄 다운로드 창 구현 계획서

## 1. 목표

현재 Kemono Downloader 안에 별도의 두 번째 창을 추가해, 사용자가 태그를 조합해 Danbooru, Gelbooru, Rule34, Rule34Video에서 이미지 또는 영상을 일괄 검색하고 다운로드할 수 있게 한다.

새 창의 핵심 기능은 다음과 같다.

1. 포지티브 태그 입력: 지정한 태그가 붙은 콘텐츠만 검색한다.
2. 네거티브 태그 입력: 지정한 태그가 붙은 콘텐츠는 제외한다.
3. 태그 종류 선택: 일반 태그, 아티스트 태그, 캐릭터/시리즈 태그 등을 구분해 입력하거나 자동완성한다.
4. 사이트 선택: Danbooru, Gelbooru, Rule34, Rule34Video 중 하나 또는 여러 개를 선택한다.
5. 이미지/영상 선택: 이미지, 영상, 둘 다를 선택해 다운로드한다.
6. 결과 수 제한, 평점 필터, 최소 점수, 저장 위치, 중복 방지 같은 기존 Booru/Rule34 설정과 연동한다.
7. 검색 결과 미리보기 또는 카운트 확인 후 다운로드를 시작할 수 있게 한다.

## 2. 현재 코드 분석 결과

### 2.1 이미 사용 가능한 기능

현재 프로그램에는 Booru 계열 다운로드 기능이 이미 들어 있다.

- `src/utils/network_utils.py`
  - Danbooru URL 감지
  - Gelbooru URL 감지
  - Rule34 URL 감지
  - Rule34Video 단일 영상 URL 감지
- `src/ui/classes/downloader_factory.py`
  - `danbooru`, `gelbooru` -> `BooruDownloadThread`
  - `rule34` -> `Rule34DownloadThread`
  - `rule34video` -> `Rule34VideoDownloadThread`
- `src/core/booru_client.py`
  - Danbooru 태그 검색 URL
  - Danbooru 단일 포스트 URL
  - Gelbooru 태그 검색 URL
  - Gelbooru 단일 포스트 URL
- `src/ui/classes/booru_downloader_thread.py`
  - Danbooru/Gelbooru 다운로드
  - 점수 필터
  - 평점 필터
  - 이미지/영상 선택
  - 블랙리스트/화이트리스트
  - 중복 hash DB
  - 스마트 캐릭터/씬 폴더 정렬
- `src/ui/classes/rule34_downloader_thread.py`
  - Rule34 태그 검색 API 다운로드
  - 페이지 단위 수집
  - 멀티스레드 다운로드
  - 점수/평점/미디어 타입 필터
  - 블랙리스트/화이트리스트
  - 다운로드 hash DB 기록
- `src/core/rule34video_client.py`
  - Rule34Video 단일 영상 페이지에서 다운로드 링크와 태그를 추출
  - 1080p, 720p, 480p, 360p 순서로 적절한 영상 링크 선택
- `src/ui/dialogs/Rule34SettingsDialog.py`
  - Rule34/Booru 공통 설정 창
  - API credentials 저장
  - rating, min score, max downloads
  - 이미지/영상 다운로드 여부
  - custom blacklist, whitelist
  - 캐릭터 DB 기반 자동완성

### 2.2 새로 필요한 기능

현재 코드에는 “태그 조합을 별도 창에서 만들고 여러 사이트에 동시에 적용하는 UI”가 없다.

또한 Rule34Video는 단일 영상 URL 다운로드만 구현되어 있다. 즉, Rule34Video까지 태그 기반 일괄 다운로드에 포함하려면 다음 단계가 새로 필요하다.

- Rule34Video 태그 검색 URL 또는 검색 HTML을 분석한다.
- 태그 검색 결과 페이지에서 영상 상세 URL 목록을 수집한다.
- 수집한 상세 URL마다 기존 `fetch_rule34video_data()`를 호출해 실제 다운로드 링크를 얻는다.
- 이 과정을 담당하는 `Rule34VideoBatchDownloadThread` 또는 공통 batch controller를 만든다.

## 3. 제안하는 새 창 구조

새 창 이름 후보:

- `TagBatchDownloadDialog`
- 사용자 표시명: `Tag Batch Downloader`

파일 위치:

- `src/ui/dialogs/TagBatchDownloadDialog.py`

창 형태:

- PyQt5 `QDialog`
- 메인 창의 자식 창으로 실행
- 다운로드 중에도 메인 창과 신호를 공유할 수 있게 parent를 `DownloaderApp`으로 둔다.

## 4. UI 구성안

### 4.1 상단: 사이트 선택

체크박스 또는 탭으로 구성한다.

- Danbooru
- Gelbooru
- Rule34
- Rule34Video

추천 방식:

- 첫 버전은 체크박스 방식
- 여러 사이트를 동시에 선택하면 같은 태그 쿼리로 순차 다운로드
- 각 사이트별 결과 수와 실패 수를 하단 로그에 따로 표시

### 4.2 태그 입력 영역

필드:

- Positive Tags
- Negative Tags
- Artist Tags
- Character Tags
- General Tags

동작:

- Positive Tags는 최종 검색 쿼리에 반드시 포함된다.
- Negative Tags는 검색 쿼리에는 `-tag` 형태로 넣고, 다운로드 전에도 한 번 더 제외 필터로 검사한다.
- Artist Tags는 사이트별 태그 문법에 맞게 일반 태그와 함께 검색하되, 자동완성에서 artist category를 우선 표시한다.
- Character Tags와 General Tags도 동일하게 쿼리에 합쳐지지만 UI에서 분류해 사용자가 관리하기 쉽게 한다.

입력 방식:

- comma separated text
- 자동완성
- 추천 태그 클릭 시 chip처럼 추가
- 태그 삭제 버튼

예시:

```text
Positive: 2b, nier_automata
Negative: guro, scat, furry
Artist: artist_name
General: solo, highres
```

### 4.3 필터 영역

기존 Rule34/Booru 설정과 맞춰 다음 항목을 제공한다.

- Media Type: Images, Videos, Both
- Rating: All, Safe only, Questionable + Safe, Explicit only
- Min Score
- Max Downloads
- Max Pages
- Sort by: Newest, Oldest, Score
- Duplicate handling: 기존 hash DB 사용
- Output folder
- Create subfolder by source
- Create subfolder by query
- Create subfolder by artist/tag

### 4.4 태그 자동완성 영역

검색창 아래에 추천 목록을 표시한다.

표시 컬럼:

- tag name
- category
- count
- source

카테고리 색상:

- Artist
- General
- Character
- Copyright/Series
- Meta
- Unknown

### 4.5 결과 미리보기

첫 구현에서는 선택 기능으로 둔다.

- Search Preview 버튼
- 각 사이트별 예상 결과 수
- 샘플 20개 정도의 post ID, rating, score, type 표시
- 썸네일 미리보기는 2차 구현으로 미룬다.

### 4.6 하단: 실행/로그

버튼:

- Search Preview
- Start Batch Download
- Pause
- Resume
- Cancel
- Save Preset
- Load Preset

로그:

- 사이트별 검색 시작/완료
- 다운로드 성공/스킵/실패 개수
- 제외된 네거티브 태그 사유
- 중복 hash로 건너뛴 항목

## 5. 태그 쿼리 생성 규칙

공통 모델:

```python
TagBatchQuery(
    sources=["danbooru", "gelbooru", "rule34"],
    positive_tags=["2b", "nier_automata"],
    negative_tags=["guro", "scat"],
    artist_tags=["artist_name"],
    general_tags=["solo"],
    media_types=["image", "video"],
    rating_filter="all",
    min_score=0,
    max_downloads=500,
)
```

최종 태그 목록:

```text
positive + artist + character + general + negative_as_minus
```

예시:

```text
2b nier_automata artist_name solo -guro -scat
```

URL 생성 예시:

```text
Danbooru:
https://danbooru.donmai.us/posts?tags=2b+n彼_automata+solo+-guro

Gelbooru:
https://gelbooru.com/index.php?page=post&s=list&tags=2b+nier_automata+solo+-guro

Rule34:
https://rule34.xxx/index.php?page=post&s=list&tags=2b+nier_automata+solo+-guro
```

주의:

- 태그는 공백 대신 `_`를 기본으로 사용한다.
- URL 인코딩은 `urllib.parse.urlencode()` 또는 `quote_plus()`로 처리한다.
- 네거티브 태그는 사이트가 지원해도, post tags에서 2차 검증한다.
- 사이트별 태그 개수 제한이 있을 수 있으므로 경고를 표시한다.

## 6. 태그 자동완성 설계

새 모듈 후보:

- `src/core/tag_search_client.py`

공통 인터페이스:

```python
class TagSuggestion:
    name: str
    category: str
    count: int
    source: str

class TagSearchClient:
    def search_tags(self, source, query, category=None, limit=20):
        ...
```

사이트별 provider:

- `DanbooruTagProvider`
- `GelbooruTagProvider`
- `Rule34TagProvider`
- `Rule34VideoTagProvider`

캐시:

- `appdata/tag_cache.db`
- 동일 검색어는 일정 시간 캐싱
- 네트워크 실패 시 캐시 결과를 먼저 보여준다.

자동완성 UX:

- 입력 후 300ms debounce
- QThread로 네트워크 검색
- UI freeze 방지
- 사이트별 결과를 합쳐 보여주되 source badge 표시

현재 재사용 가능 자원:

- `Rule34SettingsDialog`의 `MultiCompleter`
- `characters.db` 기반 캐릭터 자동완성
- `r34_api_key`, `r34_user_id` 설정값

## 7. 다운로드 실행 구조

### 7.1 추천 구조

새 controller를 만든다.

- `src/ui/classes/tag_batch_download_thread.py`
- 또는 `src/core/tag_batch_manager.py`

역할:

1. TagBatchQuery를 받아 사이트별 실제 검색 URL을 만든다.
2. 기존 다운로드 스레드를 순차 또는 병렬로 실행한다.
3. 진행률/로그/취소/일시정지를 메인 창에 전달한다.
4. 모든 사이트가 끝나면 전체 완료 신호를 보낸다.

### 7.2 기존 스레드 재사용

Danbooru/Gelbooru:

- 기존 `BooruDownloadThread` 재사용 가능
- 입력 URL만 새 창에서 만들어 넘긴다.

Rule34:

- 기존 `Rule34DownloadThread` 재사용 가능
- `tags=` 쿼리를 가진 Rule34 URL을 만들어 넘긴다.

Rule34Video:

- 기존 `Rule34VideoDownloadThread`는 단일 URL만 처리한다.
- 새로 `Rule34VideoBatchDownloadThread`를 만들거나, batch manager가 영상 URL 목록을 순회하며 기존 thread 또는 다운로드 함수를 호출한다.

추천:

- 1차 구현에서는 Danbooru/Gelbooru/Rule34만 완성한다.
- Rule34Video는 “검색 결과 URL 수집 기능”을 별도 단계로 구현한다.

## 8. 메인 창 통합 방법

수정 파일:

- `src/utils/resolution.py`
- `src/ui/main_window.py`

추가 UI 위치:

현재 `resolution.py`에는 Booru credentials와 Rule34/Booru settings 버튼이 있다.

```python
main_app.booru_creds_input
main_app.rule34_settings_btn
```

여기에 새 버튼을 추가한다.

```python
main_app.tag_batch_btn = QPushButton("🏷️ Tag Batch")
booru_inputs_layout.addWidget(main_app.tag_batch_btn, stretch=1)
```

또는 항상 보이는 상단/하단 버튼으로 추가할 수도 있다.

권장:

- Booru/Rule34 URL 입력 시만 나타나는 버튼이 아니라, 항상 열 수 있는 버튼으로 둔다.
- 이유: 사용자는 URL을 직접 입력하지 않고 태그 창에서 사이트를 고를 것이기 때문이다.

메서드:

```python
def _show_tag_batch_dialog(self):
    from .dialogs.TagBatchDownloadDialog import TagBatchDownloadDialog
    dialog = TagBatchDownloadDialog(self)
    dialog.exec_()
```

연결:

```python
self.tag_batch_btn.clicked.connect(self._show_tag_batch_dialog)
```

## 9. 파일별 구현 계획

### 9.1 신규 파일

`src/ui/dialogs/TagBatchDownloadDialog.py`

- 새 창 UI
- 태그 입력
- 사이트 선택
- 검색 미리보기
- 다운로드 시작/취소

`src/core/tag_query.py`

- 태그 정규화
- positive/negative 병합
- 사이트별 URL 생성
- 쿼리 검증

`src/core/tag_search_client.py`

- 태그 자동완성 provider
- 네트워크 검색
- 태그 카테고리 매핑

`src/ui/classes/tag_batch_download_thread.py`

- 사이트별 기존 다운로드 스레드 실행 관리
- 전체 진행률 취합
- 취소/일시정지 처리

`src/ui/classes/rule34video_batch_download_thread.py`

- Rule34Video 태그 검색 결과 URL 수집
- 기존 `fetch_rule34video_data()` 재사용
- 영상 다운로드 및 DB 기록

`tests/test_tag_query.py`

- positive/negative 태그 조합 테스트
- URL 인코딩 테스트
- 사이트별 URL 생성 테스트

### 9.2 수정 파일

`src/utils/resolution.py`

- 새 버튼 추가

`src/ui/main_window.py`

- `_show_tag_batch_dialog()` 추가
- 새 버튼 signal 연결
- 필요 시 tag batch thread signal 연결

`src/config/constants.py`

- 새 설정 키 추가
  - `TAG_BATCH_LAST_SOURCES_KEY`
  - `TAG_BATCH_LAST_POSITIVE_KEY`
  - `TAG_BATCH_LAST_NEGATIVE_KEY`
  - `TAG_BATCH_OUTPUT_MODE_KEY`

`src/core/rule34video_client.py`

- 태그 검색 결과 페이지를 읽어 영상 상세 URL 목록을 반환하는 함수 추가

예:

```python
def search_rule34video_by_tags(tags, page=1, logger_func=print):
    ...
```

## 10. 구현 단계

### 1단계: MVP 창 구현

목표:

- 새 창을 연다.
- Positive/Negative 태그를 입력한다.
- Danbooru/Gelbooru/Rule34 중 사이트를 선택한다.
- URL을 생성해 기존 다운로드 스레드를 실행한다.

완료 기준:

- 새 버튼으로 창이 열린다.
- `2b, solo` 같은 positive 태그와 `guro` 같은 negative 태그로 URL이 생성된다.
- 기존 Booru/Rule34 다운로더가 실행된다.
- 다운로드 성공/스킵 개수가 메인 로그에 출력된다.

### 2단계: 필터/설정 연동

목표:

- 이미지/영상 체크박스
- 평점 필터
- 최소 점수
- 최대 다운로드 수
- 저장 폴더
- 기존 Rule34/Booru settings와 연동

완료 기준:

- 새 창 설정이 기존 `r34_*` 설정과 충돌하지 않는다.
- 새 창에서 지정한 값이 이번 batch에 우선 적용된다.
- 기존 설정 창은 그대로 작동한다.

### 3단계: 태그 자동완성

목표:

- Danbooru/Gelbooru/Rule34 태그 검색 provider 구현
- category/count/source 표시
- 로컬 cache DB 저장

완료 기준:

- 2글자 이상 입력하면 추천 태그가 뜬다.
- artist/general/character 구분 표시가 가능하다.
- 네트워크 실패 시 앱이 멈추지 않는다.

### 4단계: 검색 미리보기

목표:

- 다운로드 전 각 사이트에서 일부 결과를 가져와 보여준다.
- result count 또는 sample post 목록을 표시한다.

완료 기준:

- Preview에서 source, post id, score, rating, media type이 보인다.
- 사용자가 확인 후 다운로드를 시작할 수 있다.

### 5단계: Rule34Video 태그 검색 지원

목표:

- Rule34Video에서 태그 검색 결과의 영상 URL 목록을 수집한다.
- 수집된 영상 URL마다 기존 단일 영상 다운로드 로직을 재사용한다.

완료 기준:

- Rule34Video source 선택 시 태그 검색이 가능하다.
- 검색 결과 영상 URL 목록이 생성된다.
- 각 영상이 기존 품질 선택 로직으로 다운로드된다.

주의:

- 현재 코드에는 Rule34Video 검색 API가 없다.
- 구현 전 실제 사이트 검색 URL/HTML 구조 검증이 필요하다.
- 사이트 구조 변경에 취약하므로 별도 smoke test가 필요하다.

### 6단계: 저장 프리셋과 작업 큐

목표:

- 자주 쓰는 태그 조합을 저장한다.
- 여러 태그 조합을 큐에 넣어 순차 실행한다.

완료 기준:

- 프리셋 저장/불러오기 가능
- 여러 query job을 추가하고 순서대로 실행 가능

## 11. 리스크 및 대응

### 11.1 사이트별 태그 문법 차이

문제:

- Danbooru, Gelbooru, Rule34, Rule34Video가 태그 카테고리와 검색 문법을 다르게 처리할 수 있다.

대응:

- 내부에서는 공통 `TagBatchQuery`로 관리한다.
- 사이트별 URL 생성은 provider가 담당한다.
- negative tag는 서버 쿼리와 클라이언트 2차 필터를 함께 사용한다.

### 11.2 Rule34Video 검색 불확실성

문제:

- 현재 코드상 Rule34Video는 단일 영상 페이지만 처리한다.
- 태그 검색 API 또는 HTML 구조가 확인되어야 한다.

대응:

- 1차 버전에서는 Rule34Video를 비활성 또는 experimental로 표시한다.
- 2차 단계에서 검색 HTML scraper를 추가한다.
- 실패 시 사용자에게 “검색 지원 불가/사이트 구조 변경 가능성”을 명확히 보여준다.

### 11.3 API rate limit

문제:

- 태그 자동완성과 미리보기, 다운로드가 모두 API 요청을 만든다.

대응:

- debounce
- 캐시 DB
- API key/user_id 사용
- 요청 간 delay
- max pages/max downloads 제한

### 11.4 성인/민감 태그 필터

문제:

- 네거티브 태그를 잘못 입력하면 의도하지 않은 콘텐츠가 포함될 수 있다.

대응:

- 기존 `r34_custom_blacklist`, safety preset을 새 창에도 표시한다.
- “항상 적용되는 기본 제외 태그”와 “이번 검색에서만 제외할 태그”를 구분한다.

### 11.5 UI 복잡도

문제:

- 태그 종류, 사이트, 필터, 프리셋까지 한 화면에 넣으면 복잡해질 수 있다.

대응:

- 기본 탭: 사이트, 태그, 저장 위치, 시작 버튼
- 고급 탭: rating, score, max pages, cache, sorting, duplicate
- 첫 버전은 미리보기/프리셋을 후순위로 둔다.

## 12. 추천 MVP 범위

가장 먼저 만들 버전은 다음 정도가 적당하다.

포함:

- 새 `TagBatchDownloadDialog`
- 사이트 선택: Danbooru, Gelbooru, Rule34
- Positive Tags
- Negative Tags
- Image/Video 선택
- Max Downloads
- Output folder
- Start/Cancel
- 기존 다운로드 스레드 재사용

제외 또는 후순위:

- Rule34Video 태그 검색
- 썸네일 미리보기
- 태그 자동완성 전체 구현
- 프리셋
- 여러 쿼리 큐

이렇게 하면 기능을 빠르게 실제로 열어볼 수 있고, 이후 Rule34Video와 자동완성을 안정적으로 붙일 수 있다.

## 13. 최종 결론

요청한 “태그 기반 일괄 다운로드 전용 두 번째 창”은 충분히 구현 가능하다.

Danbooru, Gelbooru, Rule34는 현재 코드에 이미 태그 검색 다운로드 기반이 있으므로, 새 창에서 태그 쿼리 URL을 만들어 기존 스레드에 넘기는 방식으로 빠르게 구현할 수 있다.

Rule34Video는 현재 단일 영상 URL 다운로드만 구현되어 있으므로, 태그 검색 결과에서 영상 상세 URL 목록을 수집하는 신규 클라이언트가 필요하다. 따라서 구현 순서는 Danbooru/Gelbooru/Rule34 MVP를 먼저 완성하고, 이후 Rule34Video 검색 수집기를 추가하는 것이 가장 안전하다.
