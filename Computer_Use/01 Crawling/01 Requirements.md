요구하신 작업(삼성증권 POP 웹 화면에서 **종목코드 입력 → Enter → 화면 저장**)은 크게 2가지 방식이 있고, **방식에 따라 추천 모델이 달라집니다.**

## 1) “안정적인 자동화(권장)” = Playwright/Selenium 중심 + (개발 보조로 LLM)

* **런타임(실행 중)에는 OpenAI 모델이 꼭 필요하지 않습니다.**
  입력칸을 DOM selector로 찾아 `type()` + `Enter` 후 `screenshot()` 하면 가장 재현성이 좋습니다.
* **개발/유지보수(코드 작성, 예외처리, 로그인/세션, 캡처 조건 설계)** 용으로는
  **`gpt-5.2`** 추천 (코딩/에이전트성 작업에 최적화된 플래그십 모델) ([OpenAI Platform][1])

  * 비용/속도 우선이면 **`gpt-5-mini`**로도 충분한 경우가 많습니다(모델 패밀리 안내). ([OpenAI Platform][2])

## 2) “사람처럼 화면 보고 클릭/타이핑” = Computer Use 도구 기반 에이전트

* POP 화면이 **selector 잡기 어렵거나(프레임/가상키보드/난독화/잦은 UI 변경)**, 사람이 하는 동작처럼 처리하고 싶다면
  **`computer-use-preview`**가 목적에 정확히 맞습니다.
  OpenAI 문서에서도 **브라우저 기반 작업에 `computer-use-preview` 사용을 권장**합니다. ([OpenAI Platform][3])
* 참고로 이 모델은 **Responses API에서 “computer use tool”과 함께 쓰는 전용 모델**입니다. ([OpenAI Platform][4])
* 실무적으로는 보통 **`gpt-5.2`(오케스트레이션/계획/에러 복구) + `computer-use-preview`(GUI 액션)** 조합이 깔끔합니다. ([OpenAI Platform][1])

### 한 줄 추천

* **가능하면(대부분 가능)**: `gpt-5.2`로 Playwright 자동화 코드를 만들고, 실행은 Playwright로만. ([OpenAI Platform][1])
* **UI가 자주 바뀌거나 selector가 지옥이면**: `computer-use-preview`(실행) + `gpt-5.2`(컨트롤/복구). ([OpenAI Platform][3])

원하시면, 지금 캡처 화면 기준으로 **“Playwright로 입력칸 selector 찾는 전략(iframe/캔버스/동적 요소 대응 포함) + 캡처 저장 로직”**을 바로 설계해 드릴게요.

[1]: https://platform.openai.com/docs/models/gpt-5.2?utm_source=chatgpt.com "GPT-5.2 Model | OpenAI API"
[2]: https://platform.openai.com/docs/models?utm_source=chatgpt.com "Models | OpenAI API"
[3]: https://platform.openai.com/docs/guides/tools-computer-use?utm_source=chatgpt.com "Computer use | OpenAI API"
[4]: https://platform.openai.com/docs/models/computer-use-preview?utm_source=chatgpt.com "computer-use-preview Model | OpenAI API"
