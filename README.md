# data-go-kr-housing-mcp — 공동주택관리정보(K-apt) OpenAPI → MCP 래퍼

data.go.kr(공공데이터포털)가 제공하는 K-apt(공동주택관리정보시스템) 관련
오픈API를 Claude 커스텀 커넥터에서 조회할 수 있게 감싼 원격 MCP 서버입니다.

## 제공 도구

| 도구 | 신뢰도 | 설명 |
|---|---|---|
| `get_apt_basic_info` | **[확정]** | 단지코드로 공동주택 기본정보(관리방식·설비현황 등) 조회 |
| `call_data_go_kr_openapi` | 범용 | 그 외 모든 data.go.kr API를 직접 호출하는 확장용 도구 |

## 왜 도구가 2개뿐인가 [투명성 고지]

요청하신 7개 항목(기본정보/입찰공고/관리비/단지목록/공공서비스혜택/수의계약공지 등)
중 **공동주택 기본정보만 정확한 요청 URL·파라미터를 확인**했습니다.
data.go.kr은 자동 크롤링(robots.txt)을 차단하고 있어서, 나머지 API들의
정확한 오퍼레이션명은 로그인 후 Swagger UI에서만 확인 가능합니다.

잘못 추정한 오퍼레이션명으로 코드를 만들면 "SERVICE ERROR" 같은 모호한
오류만 반환되어 디버깅이 오히려 더 어려워지므로, 대신 **범용 호출 도구**
(`call_data_go_kr_openapi`)를 만들었습니다. 아래 절차대로 진행하시면 됩니다.

## 1단계 — 공공데이터포털 인증키 발급

1. https://www.data.go.kr 회원가입/로그인
2. 필요한 각 API 상세페이지에서 **활용신청** (대부분 자동승인, 즉시 사용 가능)
   - 공동주택 기본 정보제공 서비스: `data.go.kr/data/15058453/openapi.do`
   - 공동주택 입찰공고 정보제공 서비스: `data.go.kr/data/15058166/openapi.do`
   - (수의계약공지/단지목록/관리비 정보/공공서비스혜택 정보도 각각 검색 후 활용신청)
3. 마이페이지 → 개발계정 → **일반 인증키(Decoding)** 복사
   (data.go.kr은 계정당 인증키 1개로 승인된 모든 API에 공통 사용됩니다)

## 2단계 — 나머지 API의 정확한 스펙 확인 (중요)

각 API 상세페이지 승인 후 우측 상단 근처 **"미리보기"** 또는 Swagger UI
버튼을 누르면, 실제 요청 URL과 파라미터를 브라우저에서 바로 테스트해볼 수
있습니다. 여기서 확인한 **요청 URL 전체(엔드포인트+파라미터명)** 를 캡처하거나
복사해서 알려주시면, 해당 API도 `get_apt_basic_info`처럼 전용 도구로
만들어서 다음 버전에 추가해드리겠습니다.

임시로는 `call_data_go_kr_openapi` 도구에 그 URL과 파라미터를 그대로 넣어
바로 쓰실 수 있습니다.

## 3단계 — Render에 배포

1. `server.py`, `requirements.txt`, `README.md`를 새 GitHub 레포 루트에 업로드
2. Render 대시보드 → New → Web Service → 레포 선택
   - Build Command: `pip install -r requirements.txt`
   - Start Command: `python server.py`
3. **환경변수는 필요 없습니다** — 인증키는 서버가 아니라 각자의 커넥터
   등록 URL에서 받습니다.
4. Deploy 완료 후 서버 주소: `https://<서비스이름>.onrender.com/mcp`

## 4단계 — Claude 커스텀 커넥터 등록 [인증 방식 변경]

여러 명(다른 소장님 등)이 서버 하나를 같이 쓸 수 있도록, 인증키를 URL에
직접 붙이는 방식입니다.

1. Claude.ai → Settings → Connectors → **+ Add custom connector**
2. Name: `공동주택관리정보(K-apt)` 등
3. URL: `https://<서비스이름>.onrender.com/mcp?api_key=본인의_data.go.kr_인증키`
4. OAuth Client ID/Secret은 비워두세요

**다른 소장님과 같이 쓰시는 경우**: base URL(`.../mcp` 부분, `?api_key=` 제외)만
공유하세요. 각자 자기 인증키를 붙여서 등록하면 각자의 키로 호출됩니다.
`?api_key=본인키`가 포함된 전체 URL은 개인 키 노출과 같으니 공유하지 마세요.

## 로컬 테스트

```bash
python -m venv venv
./venv/bin/pip install -r requirements.txt
PORT=8125 ./venv/bin/python server.py
```

다른 터미널 (api_key는 URL 쿼리파라미터로):
```bash
curl -N -X POST "http://127.0.0.1:8125/mcp/?api_key=발급받은키" \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-06-18","capabilities":{},"clientInfo":{"name":"test","version":"1.0"}}}'
```
`serverInfo.name: "data-go-kr-housing"` 이 포함된 응답이 오면 정상입니다.

## 확인된 API 스펙 [확정 — 공동주택 기본정보]

- 요청 URL: `http://apis.data.go.kr/1613000/AptBasisInfoServiceV3/getAphusBassInfoV3`
- 필수 파라미터: `kaptCode`(단지코드), `ServiceKey`(인증키)
- 단지코드를 모르는 경우: k-apt.go.kr에서 단지명으로 검색해 확인 가능

## 참고 — "대한민국 공공서비스(혜택) 정보"에 대해 [요확인]

이 API는 K-apt와 무관한 별개 도메인(복지 급여·지원 서비스 안내, 행정안전부
계열)입니다. 같은 서버에 넣고 싶으신지, 별도의 MCP 서버로 분리하고 싶으신지
알려주시면 그에 맞게 구성해드리겠습니다.
