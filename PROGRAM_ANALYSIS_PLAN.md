# Kemono Downloader 프로그램 분석 및 개선 계획서

## 1. 분석 목적

이 문서는 저장소의 README, 기능 설명서, 실행 진입점, UI 코드, 다운로드 매니저, 사이트별 클라이언트, 보조 서비스 코드를 기준으로 이 프로그램이 수행하는 역할과 보유 기능을 정리하고, 향후 안정화 및 개선을 위한 실행 계획을 제안한다.

분석 기준 파일:

- `readme.md`
- `features.md`
- `main.py`
- `src/ui/main_window.py`
- `src/ui/classes/downloader_factory.py`
- `src/core/api_client.py`
- `src/core/workers.py`
- `src/core/manager.py`
- `src/core/database_manager.py`
- `src/core/visual_sorter.py`
- `src/services/drive_downloader.py`
- `src/services/multipart_downloader.py`
- `src/services/updater.py`
- `src/utils/*`

## 2. 프로그램의 핵심 역할

Kemono Downloader는 여러 웹 사이트의 게시물, 첨부 파일, 이미지, 영상, 오디오, 압축 파일, 외부 링크, 텍스트 본문을 사용자가 지정한 조건에 따라 수집하고 로컬 폴더에 정리하는 PyQt5 기반 GUI 다운로드/아카이브 도구이다.

핵심 역할은 다음과 같다.

1. 여러 플랫폼 URL을 해석해 적절한 다운로더로 라우팅한다.
2. Kemono/Coomer 계열 API에서 크리에이터 또는 단일 게시물을 가져와 필터링 후 다운로드한다.
3. Bunkr, Erome, nhentai, Saint2, Discord, Rule34, MangaDex 등 사이트별 구조가 다른 콘텐츠를 전용 스레드로 처리한다.
4. 파일 종류, 키워드, 크기, 캐릭터명, 게시물 범위, 댓글/본문 등의 조건으로 다운로드 대상을 제한한다.
5. 다운로드 결과를 캐릭터명, 게시물명, 날짜, 사용자 지정 규칙에 따라 폴더와 파일명으로 정리한다.
6. 중단된 다운로드, 실패 파일, 작업 큐, 크리에이터 프로필, 다운로드 히스토리를 저장해 반복 작업과 복구를 지원한다.
7. Mega, Google Drive, Dropbox, Gofile 등 외부 링크를 추출하거나 직접 다운로드한다.
8. 이미지 압축, 썸네일 다운로드, 중복 감지, AI 기반 시각 분류 같은 후처리 기능을 제공한다.

## 3. 전체 구조

### 3.1 실행 구조

- `main.py`가 PyQt5 애플리케이션을 생성하고 `DownloaderApp` 메인 창을 실행한다.
- 앱 시작 시 전역 예외 로깅을 설정하고, `logs/uncaught_exceptions.log`에 치명적 오류를 기록한다.
- `appdata/models/model.onnx`와 `selected_tags.csv`가 존재하면 Visual Sort AI 엔진을 사전 로드한다.
- 첫 실행 사용자를 위해 `TourDialog` 안내 화면을 띄울 수 있다.

### 3.2 UI 계층

- `src/ui/main_window.py`가 메인 GUI, 입력값 수집, 세션 저장/복원, 버튼 상태 전환, 다운로드 시작/중지/완료 처리를 담당한다.
- `src/ui/dialogs/*`에는 설정, 도움말, 오류 파일, 히스토리, 즐겨찾기, 링크 내보내기, 중복 처리, 시각 분류 설정, 업데이트 확인 등의 대화상자가 있다.
- `src/ui/classes/*_downloader_thread.py`는 사이트별 QThread 다운로드 구현이다.

### 3.3 핵심 다운로드 계층

- `src/ui/classes/downloader_factory.py`는 URL 또는 서비스명을 보고 전용 다운로더를 생성한다.
- 전용 다운로더가 없는 Kemono/Coomer 계열은 `src/core/api_client.py`와 `src/core/workers.py`로 처리된다.
- `src/core/api_client.py`는 게시물 목록, 단일 게시물, 댓글, 리비전 데이터를 API로 가져온다.
- `src/core/workers.py`의 `PostProcessorWorker`는 게시물 단위로 파일 필터링, 파일명 생성, 폴더 결정, 다운로드, 중복 처리, 링크 추출, 텍스트 추출을 수행한다.
- `src/core/manager.py`는 멀티스레드 다운로드 세션, 작업 제출, 진행 상태, 크리에이터 프로필 저장을 관리한다.

### 3.4 보조 서비스 계층

- `src/services/multipart_downloader.py`: 대용량 파일을 여러 청크로 나누어 병렬 다운로드하고, 중간 `.part` 파일로 재개를 지원한다.
- `src/services/drive_downloader.py`: Mega, Google Drive, Dropbox, Gofile 다운로드를 처리하며 Mega 파일/폴더 복호화 로직을 포함한다.
- `src/services/updater.py`: GitHub 최신 릴리스를 확인하고 Windows 실행 파일 업데이트를 수행한다.
- `src/core/database_manager.py`: SQLite `library.db`로 이미지, 태그, 태그 없는 파일, 만화 갤러리 기록을 저장한다.
- `src/core/visual_sorter.py`: ONNX 모델로 이미지 태그/캐릭터 후보를 추론해 시각 분류를 돕는다.

## 4. 지원 사이트 및 다운로드 대상

코드 기준으로 확인된 지원 범위는 README보다 넓다.

### 4.1 Kemono/Coomer 계열

- Kemono: `kemono.su`, `kemono.party`, `kemono.cr`
- Coomer: `coomer.su`, `coomer.party`, `coomer.st`
- 서비스 경로 예: `/patreon/user/{id}`, `/fanbox/user/{id}`, `/onlyfans/user/{id}/post/{post_id}`
- 크리에이터 전체 게시물과 단일 게시물 다운로드를 모두 지원한다.
- Discord 서버/채널이 Kemono 계열 API에 노출된 경우 별도 Kemono Discord 다운로더가 동작한다.

### 4.2 전용 사이트 다운로더

전용 QThread 또는 클라이언트가 존재하는 사이트:

- AllPornComic/AllComic
- Bunkr
- CoomerFans
- Danbooru/Safebooru, Gelbooru, Rule34
- DeviantArt
- Discord 공식 채널 URL
- Erome
- Fap-Nation
- Hentai2Read
- HentaiFox
- Hotleaks
- MangaDex
- nhentai
- Pixeldrain
- Rule34Video
- Saint2/Turbo
- SimpCity
- Toonily

### 4.3 직접 파일 호스팅

다음 링크는 URL을 직접 입력하거나 추출 링크 다운로드 대화상자에서 처리할 수 있다.

- Mega
- Google Drive
- Dropbox
- Gofile
- Pixeldrain

### 4.4 배치 다운로드

URL 입력란에 특정 도메인 키워드를 입력하면 `appdata` 폴더의 텍스트 파일을 읽어 일괄 다운로드한다.

- `kemono.cr` 또는 `kemono.su` -> `kemono.txt`
- `coomer.st` 또는 `coomer.su` -> `coomer.txt`
- `hentaifox.com` -> `hentaifox.txt`
- `allporncomic.com` -> `allporncomic.txt`
- `nhentai.net` -> `nhentai.txt`
- `fap-nation.com` 또는 `fap-nation.org` -> `fap-nation.txt`
- `saint2.su` -> `saint2.su.txt`
- `turbo.cr` -> `turbo.cr.txt`
- `hentai2read.com` -> `hentai2read.txt`
- `rule34video.com` -> `rule34video.txt`

## 5. 주요 기능 분석

### 5.1 URL 해석 및 라우팅

- `extract_post_info()`가 URL에서 서비스명, 사용자 ID, 게시물 ID를 추출한다.
- `create_downloader_thread()`가 서비스별 전용 QThread를 생성한다.
- 전용 다운로더가 없으면 Kemono/Coomer API 기반 일반 다운로드 흐름으로 이동한다.
- 일부 URL은 쿠키가 필수이며, 쿠키가 없으면 사용자에게 안내 대화상자를 띄운다.

### 5.2 다운로드 모드

- 전체 파일 다운로드
- 이미지만 다운로드
- 영상만 다운로드
- 압축 파일만 다운로드
- 오디오만 다운로드
- 외부 링크만 추출
- 게시물 설명 또는 댓글 텍스트 추출
- Discord 메시지 PDF 저장
- 썸네일만 다운로드
- 게시물 리비전 파일까지 포함해 다운로드

### 5.3 필터링 기능

- 캐릭터명/시리즈명 필터
- 필터 범위: 제목, 파일명, 제목+파일명, 댓글
- 키워드 기반 건너뛰기
- 키워드 적용 범위: 게시물, 파일, 둘 다
- `[200]` 같은 크기 명령으로 지정 MB보다 작은 파일 제외
- 시작 페이지/종료 페이지 지정
- 압축 파일 건너뛰기
- 게시물 본문 HTML 안의 이미지 추가 스캔
- 특수 명령:
  - `[ao]`: archive only
  - `[.tld]`: 다운로드 도메인 override
  - `[sfp-N]`: 별도 threshold 명령
  - `[unknown]`: 알 수 없는 항목 처리 모드

### 5.4 폴더 및 파일명 정리

- 다운로드 위치 지정 및 없는 폴더 생성 확인
- `Known.txt` 또는 입력 필터를 이용한 캐릭터별 하위 폴더 생성
- 게시물별 하위 폴더 생성
- 게시물 폴더 날짜 prefix 지원
- 단일 게시물 사용자 지정 폴더명
- 파일명에서 특정 단어 제거
- 불법 파일명 문자 제거
- Manga/Comic 모드에서 날짜, 게시물 제목, 게시물 ID, 전역 번호, 사용자 지정 포맷 기반 파일명 생성
- 파일명 충돌 시 숫자 suffix로 회피

### 5.5 성능 및 복원력

- 크리에이터 전체 다운로드 시 게시물 단위 멀티스레딩 지원
- 단일 게시물에서 파일 단위 병렬 다운로드 지원
- 최대 스레드 수는 상수로 제한되어 있으며 과도한 입력 시 경고/캡 적용
- 대용량 파일 multipart 다운로드 지원
- multipart 다운로드는 완성된 청크 파일을 재사용해 재개할 수 있다.
- 일시정지/재개/취소 이벤트를 worker와 청크 다운로드가 공유한다.
- API 요청에는 재시도와 rate limit 대기 로직이 있다.
- 세션 파일을 `.tmp`에 먼저 쓰고 교체하는 방식으로 손상 위험을 낮춘다.

### 5.6 세션, 큐, 히스토리

- 실행 중 세션을 `session.json` 형태로 저장한다.
- 앱 재시작 시 미완료 세션을 감지해 UI를 복원하고 이어받을 수 있다.
- 처리된 게시물 ID, 실패 파일, 남은 큐, 다운로드 해시를 복원한다.
- 개별 작업을 `appdata/jobs/job_*.json` 파일로 저장해 작업 큐를 실행한다.
- 크리에이터 프로필 JSON에 설정과 처리된 게시물 ID를 저장해 업데이트 확인에 사용한다.
- 다운로드 히스토리 대화상자와 실패 파일 대화상자가 존재한다.

### 5.7 즐겨찾기 및 업데이트 확인

- Favorite Mode에서 Favorite Artists, Favorite Posts 대화상자를 통해 계정 기반 즐겨찾기를 가져온다.
- 여러 크리에이터 프로필을 대상으로 새 게시물 여부를 확인할 수 있다.
- 새 게시물만 다운로드하는 업데이트 흐름이 있다.

### 5.8 링크 추출 및 외부 다운로드

- Only Links 모드에서 게시물 설명의 Mega, Google Drive, Dropbox 등 외부 링크를 추출한다.
- 추출 링크를 TXT/JSON으로 내보낼 수 있다.
- 추출된 Mega, Google Drive, Dropbox 링크를 선택해 앱 내부에서 직접 다운로드할 수 있다.
- Mega는 파일/폴더 키 파싱과 AES 복호화 구현을 포함한다.

### 5.9 텍스트 및 PDF 출력

- 게시물 설명 또는 댓글을 PDF, DOCX, TXT로 저장할 수 있다.
- 여러 게시물 텍스트를 단일 PDF로 합치는 옵션이 있다.
- Discord 공식 채널은 메시지 히스토리를 PDF로 저장할 수 있다.

### 5.10 이미지 후처리 및 AI 시각 분류

- Pillow가 있으면 큰 이미지를 WebP로 압축할 수 있다.
- 썸네일 URL로 변환해 미리보기 이미지만 저장할 수 있다.
- SQLite DB와 이미지 해시/pHash를 이용한 중복 관리 기반이 있다.
- ONNX Runtime 기반 Visual Sort 기능은 이미지에서 캐릭터/태그 후보를 추론하고, 후보 캐릭터와 fallback rule을 활용한다.
- Visual Sort 모델 파일은 기본 포함이 아니라 설정을 통해 다운로드 또는 배치되어야 하는 구조다.

### 5.11 설정 및 운영 기능

- QSettings 기반 설정 저장
- 언어 설정
- 테마 설정
- UI scale/window resolution 설정
- 프록시 설정
- 쿠키 텍스트 또는 Netscape `cookies.txt` 지원
- GitHub 릴리스 기반 업데이트 확인 및 Windows 실행 파일 교체
- 다운로드 완료 후 알림음, 절전, 종료 같은 후속 동작

## 6. 데이터 및 파일 저장 구조

주요 저장 위치:

- `appdata/cookies.txt`: 기본 쿠키 파일 후보
- `appdata/jobs/*.json`: 작업 큐 파일
- `appdata/models/model.onnx`: Visual Sort 모델
- `appdata/models/selected_tags.csv`: Visual Sort 태그 목록
- `AppData/library.db`: SQLite 라이브러리 DB
- `logs/uncaught_exceptions.log`: 치명적 예외 로그
- 크리에이터 프로필 JSON: 크리에이터 설정과 처리된 게시물 ID 저장
- 다운로드 위치: 사용자가 GUI에서 지정

## 7. 현재 강점

1. 사이트 지원 폭이 넓다.
2. GUI에서 고급 필터와 파일 정리 기능을 직접 제어할 수 있다.
3. 세션 복원, 큐, 실패 파일 재시도 등 대량 다운로드에 필요한 운영 기능이 있다.
4. 일반 Kemono/Coomer 흐름과 사이트별 전용 다운로더가 분리되어 확장성이 있다.
5. multipart 다운로드와 멀티스레딩으로 대용량/대량 작업에 대응한다.
6. 링크 추출, 외부 클라우드 다운로드, 텍스트/PDF 저장 등 단순 파일 다운로드 이상의 아카이브 기능을 갖고 있다.
7. Visual Sort, DB 기록, 중복 감지처럼 후처리 자동화 기능이 있다.

## 8. 현재 위험요소 및 개선 필요점

### 8.1 안정성

- 사이트별 다운로더가 많아 각 사이트 구조 변경에 취약하다.
- 다운로드 로직이 UI와 강하게 결합된 부분이 있어 회귀 테스트가 어렵다.
- 테스트 디렉터리가 발견되지 않아 자동 검증 기반이 부족하다.
- 일부 코드에는 오래된 구조와 새 구조가 함께 남아 있어 유지보수 난도가 높다.

### 8.2 보안

- 쿠키, Discord 토큰, 프록시 인증정보 등 민감 정보가 UI와 설정 경로에 들어간다.
- 공식 Discord 토큰을 특정 입력 필드에 넣는 방식은 사용성 및 보안 측면에서 위험하다.
- 업데이트 로직은 실행 파일 교체와 배치 스크립트를 사용하므로 무결성 검증 강화가 필요하다.
- `verify=False` HTTP 요청이 다수 사용되어 TLS 검증 약화 위험이 있다.

### 8.3 법적/정책 리스크

- 이 프로그램은 여러 사이트의 콘텐츠를 대량 다운로드할 수 있으므로 각 사이트 약관, 저작권, 접근 권한을 지켜야 한다.
- 쿠키 기반 접근은 사용자의 권한 범위를 넘지 않도록 안내가 필요하다.
- 성인 콘텐츠 사이트가 다수 포함되어 있어 배포 문서와 사용 안내에서 책임 범위를 명확히 해야 한다.

### 8.4 UX

- 기능 수가 많아 초보 사용자는 설정 조합을 이해하기 어렵다.
- 일부 특수 명령은 문서화가 충분하지 않으면 오입력 가능성이 크다.
- 사이트별 필수 쿠키/토큰/제약 조건을 URL 입력 단계에서 더 명확히 안내할 필요가 있다.

### 8.5 유지보수성

- 사이트별 URL 판별, 배치 파일명, 다운로더 매핑이 여러 위치에 흩어져 있다.
- 설정 키와 UI 상태 저장 항목이 많아 스키마 문서화가 필요하다.
- 다운로드 결과/실패/히스토리/DB 기록의 책임 경계가 더 명확해질 필요가 있다.

## 9. 개선 목표

1. 지원 사이트와 기능을 정확히 문서화하고 사용자 혼란을 줄인다.
2. 다운로드 라우팅과 사이트별 설정을 중앙화한다.
3. 핵심 로직에 자동 테스트를 도입해 사이트별 변경 대응 속도를 높인다.
4. 쿠키/토큰/업데이트 보안을 강화한다.
5. 세션 복원, 실패 재시도, multipart 재개 기능을 더 안정적으로 만든다.
6. UI를 고급 사용자용 기능은 유지하되 초보자도 안전하게 쓸 수 있게 정리한다.

## 10. 실행 계획

### 1단계: 문서 및 기능 인벤토리 정리

기간: 1주

작업:

- README와 `features.md`를 코드 기준으로 갱신한다.
- 지원 사이트 목록을 “공식 문서 기준”과 “코드상 구현 기준”으로 구분한다.
- 배치 모드 파일명과 URL 예시를 표로 정리한다.
- 특수 명령 `[ao]`, `[.tld]`, `[sfp-N]`, `[unknown]`을 사용자 문서에 추가한다.
- 사이트별 쿠키/토큰 필요 여부와 제한사항을 정리한다.

산출물:

- 최신 사용자 가이드
- 지원 사이트 매트릭스
- 설정/명령어 레퍼런스

### 2단계: 안정화 및 테스트 기반 구축

기간: 2-3주

작업:

- `extract_post_info()`에 URL 파싱 단위 테스트를 추가한다.
- `parse_commands_from_text()`와 파일/텍스트 유틸 함수 테스트를 추가한다.
- `downloader_factory.py`에 URL별 라우팅 테스트를 추가한다.
- 세션 저장/복원 JSON 스키마 테스트를 추가한다.
- API 응답 fixture를 이용해 Kemono/Coomer 기본 흐름을 네트워크 없이 검증한다.
- 사이트별 전용 다운로더는 최소한 URL 판별과 데이터 변환 테스트부터 작성한다.

산출물:

- 기본 테스트 스위트
- 회귀 테스트용 fixture
- CI에서 실행 가능한 검증 명령

### 3단계: 구조 개선

기간: 3-4주

작업:

- 지원 사이트 정의를 중앙 설정 파일 또는 registry 형태로 통합한다.
- 배치 모드 정의도 같은 registry에서 읽도록 정리한다.
- `DownloaderApp.start_download()`의 책임을 입력 검증, 설정 구성, 라우팅, 실행으로 분리한다.
- 민감 정보 입력과 일반 필터 입력을 분리한다.
- 다운로드 결과 이벤트 모델을 정리해 UI, 히스토리, 실패 목록, DB 기록이 같은 이벤트를 공유하게 한다.

산출물:

- 사이트 registry
- 다운로드 설정 dataclass 또는 명시적 schema
- 분리된 다운로드 실행 서비스

### 4단계: 보안 강화

기간: 2주

작업:

- 쿠키/토큰 저장 정책을 명확히 한다.
- Discord 토큰 입력 전용 UI와 경고 문구를 추가한다.
- 업데이트 다운로드 파일에 checksum 또는 서명 검증을 도입한다.
- `verify=False` 사용 지점을 목록화하고 가능한 곳부터 TLS 검증을 복구한다.
- 로그에 쿠키/토큰/민감 헤더가 출력되지 않도록 필터링한다.

산출물:

- 보안 정책 갱신
- 민감 정보 마스킹 로직
- 업데이트 무결성 검증

### 5단계: 사용자 경험 개선

기간: 2-3주

작업:

- 사이트별 입력 도움말을 URL 입력 근처에 제공한다.
- 다운로드 모드와 필터 조합이 충돌할 때 사전 경고를 표시한다.
- Only Links 모드, Text 모드, Manga 모드, Visual Sort 모드를 단계형 설정으로 정리한다.
- 작업 큐 화면을 별도 목록으로 보여주고 상태, 남은 작업, 실패 작업을 표시한다.
- 초보자 기본 모드와 고급 설정 모드를 분리한다.

산출물:

- 개선된 메인 UI 흐름
- 작업 큐 관리 화면
- 모드별 안내와 사전 검증

### 6단계: 사이트별 유지보수 체계

기간: 지속 운영

작업:

- 각 사이트 클라이언트에 “입력 URL 예시, 필요한 인증, 산출 데이터 구조, 실패 유형”을 문서화한다.
- 사이트 구조 변경 감지를 위한 smoke test URL 목록을 관리한다.
- `yt-dlp.exe` 의존 사이트는 버전 확인 및 교체 절차를 문서화한다.
- 외부 사이트 변경으로 실패 시 사용자에게 원인을 구분해 보여준다.

산출물:

- 사이트별 유지보수 문서
- smoke test 목록
- 장애 유형별 사용자 메시지

## 11. 우선순위 제안

가장 먼저 처리할 항목:

1. README와 기능 문서 갱신
2. URL 파싱/라우팅 테스트 추가
3. 쿠키/토큰 입력 방식 정리
4. 세션 복원과 실패 재시도 테스트
5. 지원 사이트 registry 도입

중기적으로 처리할 항목:

1. `start_download()` 분리
2. 사이트별 다운로더 유지보수 문서화
3. 작업 큐 UI 개선
4. 업데이트 무결성 검증
5. Visual Sort 설정/모델 다운로드 UX 개선

장기적으로 처리할 항목:

1. 핵심 다운로드 엔진과 GUI의 결합도 축소
2. 플러그인식 사이트 다운로더 구조 검토
3. 다운로드 기록/라이브러리 DB를 사용자 검색 기능으로 확장
4. 대규모 작업의 리소스 사용량 모니터링

## 12. 결론

이 프로그램은 단순한 파일 다운로더가 아니라, 여러 콘텐츠 플랫폼의 게시물과 외부 링크를 조건별로 수집하고 정리하는 고기능 아카이브 도구이다. 이미 지원 사이트, 필터링, 큐, 복원, 실패 재시도, PDF 출력, multipart, Visual Sort 등 기능 범위가 넓다.

다만 기능이 빠르게 확장된 만큼 문서, 테스트, 보안, 라우팅 구조의 정리가 다음 단계의 핵심이다. 우선은 기능 인벤토리와 테스트 기반을 세우고, 이후 사이트 registry와 다운로드 설정 schema를 도입하면 유지보수성과 안정성이 크게 좋아질 것이다.
