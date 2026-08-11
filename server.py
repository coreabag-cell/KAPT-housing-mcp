"""
data.go.kr 공동주택관리정보(K-apt) OpenAPI -> MCP 래퍼 서버 (다중 사용자 지원 버전)

국토교통부가 공공데이터포털(data.go.kr)을 통해 제공하는 공동주택관리정보시스템(K-apt)
관련 오픈API를 MCP 도구로 감싸서 Claude 커스텀 커넥터에서 사용할 수 있게 합니다.

배포: Render (Web Service, Python)
전송 방식: Streamable HTTP

인증 방식 [중요 — 이전 버전과 다름]
------------------------------------
이 서버는 인증키를 환경변수에 저장하지 않습니다. 대신 Claude 커스텀 커넥터에
등록하는 URL 자체에 각자의 인증키를 쿼리파라미터로 붙입니다:

    https://<서비스이름>.onrender.com/mcp?api_key=본인이_발급받은_data.go.kr_인증키

이렇게 하면 여러 명(다른 관리사무소장님 등)이 서버 하나를 같이 쓰면서도,
각자 자기 인증키로 호출됩니다. 서버의 base URL(?api_key= 없는 부분)만
공개해도 안전합니다 — api_key가 없으면 아무 것도 조회할 수 없습니다.

포함된 도구
------------
1. get_apt_basic_info   [확정] — 공동주택 기본정보 (AptBasisInfoServiceV3)
   요청 URL이 명확히 확인된 서비스만 전용 도구로 만들었습니다.

2. call_data_go_kr_openapi  [범용/확장용] — 그 외 모든 data.go.kr API를
   호출할 수 있는 범용 도구:
   - 공동주택 입찰공고 정보제공 서비스
   - 공동주택 수의계약 공지 정보제공 서비스
   - 공동주택 단지목록/단지코드 조회
   - 공동주택 관리비 정보(월별 관리비 내역)

   각 서비스의 정확한 요청 URL을 Swagger UI에서 확인하신 뒤 알려주시면,
   전용 도구로 승격시켜 드릴 수 있습니다.

필요 사전 준비
--------------
1. https://www.data.go.kr 회원가입 및 로그인
2. 필요한 각 API 상세페이지에서 "활용신청" (대부분 자동승인)
   - 공동주택 기본 정보제공 서비스: data.go.kr/data/15058453/openapi.do
   - 공동주택 입찰공고 정보제공 서비스: data.go.kr/data/15058166/openapi.do
   - (기타 필요한 서비스도 각각 활용신청)
3. 마이페이지 > 개발계정 에서 발급받은 "일반 인증키(Decoding)" 복사
   -> Claude 커넥터 등록 URL의 ?api_key= 뒤에 붙여서 사용
"""

import os
import json
import httpx
from mcp.server.fastmcp import FastMCP, Context

PORT = int(os.environ.get("PORT", 8000))

mcp = FastMCP(
    name="data-go-kr-housing",
    stateless_http=True,
    host="0.0.0.0",
    port=PORT,
)


def _get_api_key(ctx: Context) -> str | None:
    """현재 요청 URL의 ?api_key= 쿼리파라미터에서 인증키를 읽어옵니다."""
    req = ctx.request_context.request
    if req is None:
        return None
    return req.query_params.get("api_key")


def _missing_key_message() -> str:
    return (
        "이 요청에 api_key가 없습니다. Claude 커스텀 커넥터 등록 시 URL을 "
        "'https://<서비스이름>.onrender.com/mcp?api_key=본인의_data.go.kr_인증키' 형태로 "
        "입력했는지 확인해주세요. 인증키는 https://www.data.go.kr 마이페이지에서 발급받을 수 있습니다."
    )


@mcp.tool()
async def get_apt_basic_info(kapt_code: str, ctx: Context) -> str:
    """[확정] 공동주택 기본정보를 조회합니다 (국토교통부_공동주택 기본 정보제공 서비스, AptBasisInfoServiceV3).

    법정동주소, 분양형태, 난방방식, 연면적, 동수, 세대수 등 단지 기본정보와
    일반관리/경비관리/청소관리 방식 및 계약업체 등 상세 관리정보를 제공합니다.

    Args:
        kapt_code: K-apt 단지코드 (예: "A10027875"). 단지코드를 모르는 경우
                   K-apt 홈페이지(k-apt.go.kr)에서 단지명으로 검색해 확인할 수 있습니다.
    """
    api_key = _get_api_key(ctx)
    if not api_key:
        return _missing_key_message()

    url = "http://apis.data.go.kr/1613000/AptBasisInfoServiceV3/getAphusBassInfoV3"
    params = {"kaptCode": kapt_code, "ServiceKey": api_key, "_type": "json"}

    async with httpx.AsyncClient(timeout=15.0) as client:
        try:
            resp = await client.get(url, params=params)
            resp.raise_for_status()
        except httpx.HTTPStatusError as e:
            return f"data.go.kr API 오류 (status {e.response.status_code}): {e.response.text[:500]}"
        except httpx.RequestError as e:
            return f"data.go.kr API 요청 실패: {e}"

    return resp.text


@mcp.tool()
async def call_data_go_kr_openapi(base_url: str, params: str, ctx: Context) -> str:
    """[범용/확장용] data.go.kr의 임의의 공공데이터 OpenAPI를 호출합니다.

    get_apt_basic_info로 커버되지 않는 K-apt 관련 API(입찰공고, 수의계약공지,
    단지목록, 관리비 정보 등)나 그 외 data.go.kr의 다른 오픈API를 호출할 때
    사용합니다. ServiceKey 파라미터는 자동으로 채워지므로 params에 넣지
    마세요.

    사용 전 확인사항: base_url과 필요 파라미터명은 data.go.kr 해당 API
    상세페이지의 Swagger UI("미리보기")에서 정확히 확인한 뒤 사용해야 합니다.
    잘못된 오퍼레이션명을 넣으면 SERVICE ERROR 또는 빈 응답이 반환됩니다.

    Args:
        base_url: 오퍼레이션까지 포함한 전체 요청 URL.
                  예: "http://apis.data.go.kr/1613000/AptListService3/getSigunguAptList3"
        params: ServiceKey를 제외한 나머지 쿼리 파라미터를 JSON 문자열로.
                예: '{"sigunguCode": "11680", "pageNo": "1", "numOfRows": "50"}'
    """
    api_key = _get_api_key(ctx)
    if not api_key:
        return _missing_key_message()

    try:
        parsed_params = json.loads(params) if params else {}
    except json.JSONDecodeError as e:
        return f"params가 올바른 JSON 형식이 아닙니다: {e}"

    parsed_params["ServiceKey"] = api_key
    parsed_params.setdefault("_type", "json")

    async with httpx.AsyncClient(timeout=20.0) as client:
        try:
            resp = await client.get(base_url, params=parsed_params)
            resp.raise_for_status()
        except httpx.HTTPStatusError as e:
            return f"data.go.kr API 오류 (status {e.response.status_code}): {e.response.text[:500]}"
        except httpx.RequestError as e:
            return f"data.go.kr API 요청 실패: {e}"

    return resp.text


if __name__ == "__main__":
    mcp.run(transport="streamable-http")
