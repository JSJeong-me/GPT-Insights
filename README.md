# GPT-Insights [[교안]](https://drive.google.com/file/d/1WWqUTpISmoBB2VhG7Jb__s5dp5bkints/view?usp=sharing) - [[실습]](https://docs.google.com/document/d/13mpJl4we-SDYFB5T27oBiZPIC1qBRpTJnYVu1E2owCQ/edit?usp=sharing)
<!---
### [[GPT 업무활용]](https://docs.google.com/document/d/1TB6skjB6Iq1kDpSO1Omrwz25-TFsrFClQrUsSlH_Yv0/edit?usp=sharing) - providing the latest insights on popular trends in GPT
-->
-----

### 과정 목표: LLM 개발 Framework이 제공하는 메모리, 체인, 에이전트 기능을 활용하여 복잡한 작업을 수행하는 앱 개발

-----

### 2024년 8월 30일 금요일 09:00 🕤 ~ 18:00 🕜

-----
0. [프로그램의 진화과정](https://github.com/JSJeong-me/GPT-Insights/blob/main/images/Program-1.png)

   [자연어와 프로그램의 경계](https://github.com/JSJeong-me/GPT-Insights/blob/main/images/Program-2.png)

2. [GPT3.5 GPT4 Review와 GPT5 에 대해 미리 알아보기](https://drive.google.com/file/d/18dVgDszcWE5TkBf-arUrZsWS7WIXlbRc/view?usp=sharing)

   - [Embedding](https://platform.openai.com/tokenizer)
   - [Reinforcement Learning Human Feedback (RLHF)](https://drive.google.com/file/d/1lUynjlMYPFcxT2NSSh-44V28Vxvx52vN/view?usp=sharing)
   - [Prompt 란?](https://platform.openai.com/docs/examples)
   - [RAG(Retrieve Augmented Generation)](https://drive.google.com/file/d/1Bm4cYqmvLNe_bFzm6B3FUgBXaoP5ARbl/view) [[실습 프로그램]](https://docs.google.com/spreadsheets/d/1BB3IV0N7H33icN4mh9D52mpF4oaxJcI0srs71-XGs8I/edit#gid=0)   [[LIVE-DEMO](http://3.36.196.66:8501)]

     ![RAG](https://github.com/JSJeong-me/ProDiscovery2LLM/assets/54794815/b06f1ae9-cd23-46ab-b734-2c332541adca)

   - [Fine-tuning Model](https://drive.google.com/file/d/1KQ4TgmXeb5-bIY_rXCKPMEdT_YRmnlYf/view?usp=sharing)
     
     1) [학습데이터 생성](https://docs.google.com/spreadsheets/d/1sJ4X03A_DrBCC24zp_sqiQW17qhVoiOQVr5ScEmhfEo/edit#gid=5293024)
     2) [실습 예제 1](https://github.com/JSJeong-me/GPT-Finetuning/blob/main/51-LangChain-ChatBot.ipynb)

3. [추론(Reasoning)이란?](https://github.com/JSJeong-me/GPT-Graph/blob/main/Reasoning.md)

   - [Deductive(연역 추론) 과 Inductive reasoning(귀납 추론)](https://drive.google.com/file/d/122eW8CoR1a-gajicLMRpYaJGa_XOGNje/view?usp=sharing)
   - [Graph를 활용한 추론](https://neo4j.com/generativeai/)
   - ['Chain of Thought Reasoning'](https://docs.google.com/spreadsheets/d/1EVpv4AAehEdlitsoAdzzXn074SCUl9tGll1B80kCSZw/edit#gid=466944589)
   - ['Chaining Prompts'](https://docs.google.com/spreadsheets/d/1EVpv4AAehEdlitsoAdzzXn074SCUl9tGll1B80kCSZw/edit#gid=466944589)

4. [GPTs 활용](https://chat.openai.com/gpts)

   - [Multimodal](https://drive.google.com/file/d/1yY0ViA4hrq6V8UyMT9ZVQ-ydHzu2AVzY/view?usp=sharing)
   - [글쓰기](https://docs.google.com/spreadsheets/d/1HpKXHq0X0m5rSX-rBfIiyTrVEpbMIzwRZv9ki8JDxYc/edit#gid=12358067)  [Blog Writer](https://chat.openai.com/g/g-PAFR1uSJk-blog-writer)  [Blog Expert](https://chat.openai.com/g/g-PWizFQk8C-blog-expert)
   - [![resistor-2k](https://github.com/JSJeong-me/GPT-Insights/assets/54794815/81f87f77-a1ae-470e-b70b-0a621ab0950a)](https://github.com/JSJeong-me/GPT-Insights/blob/main/images/resistor-2k.png) [정답](https://jeong5431.tistory.com/entry/%EC%A0%80%ED%95%AD-%EC%83%89%EB%9D%A0-%EC%9D%BD%EB%8A%94-%EB%B0%A9%EB%B2%95)
   - [Cartoonize Me](https://chat.openai.com/g/g-X2Cy0Tv71-cartoonize-me-image-to-cartoon)


5. [Local LLM 의 필요성과 구현방안](https://drive.google.com/file/d/1bGLnr_m0CP7sDhip3cEgjpCmfYa_Injf/view?usp=sharing)

   - [Ollama](https://ollama.ai/library?sort=popular)
   - [Web browser 내에서 LLM 실행](https://drive.google.com/file/d/1f0iEYzn7YdUM_aqVWl1VnVYo4DdQebTB/view?usp=sharing)


6. [Graph와 Agent를 활용한 자동화 구현](https://github.com/JSJeong-me/GPT-Agent)

   - [다양한 Tools](https://python.langchain.com/v0.1/docs/integrations/tools/)  ex) [PassioAI](https://www.passio.ai/)
   - [Default Tools](https://python.langchain.com/v0.1/docs/modules/tools/) (간단한 실습)
   - [Graph Question & Answering](https://github.com/JSJeong-me/GPT-Graph/blob/main/01-Graph-Question.ipynb)
   - [multi-agent-collaboration](https://github.com/JSJeong-me/GPT-Agent/blob/main/20-multi-agent-collaboration.ipynb)
   - [agent_supervisor](https://github.com/JSJeong-me/GPT-Agent/blob/main/21-agent_supervisor.ipynb)
   - [hierarchical_agent_teams](https://github.com/JSJeong-me/GPT-Agent/blob/main/22-hierarchical_agent_teams.ipynb)

7. [CrewAI](https://github.com/joaomdmoura/crewai?tab=readme-ov-file)   [gpt-newspaper](https://github.com/assafelovic/gpt-newspaper/tree/master)   [[Tools]](https://docs.crewai.com/core-concepts/Tools/#available-crewai-tools)

8. [Monitoring: LangSmith](https://www.langchain.com/langsmith)

### Tavily API Key - [Sign Up](https://app.tavily.com/sign-in)
### SERP API Key - [Sign Up](https://serper.dev/)
### OpenAI API Key - [Sign Up](https://platform.openai.com/api-keys)

### [LLM APIs response time tracker](https://gptforwork.com/tools/openai-api-and-other-llm-apis-response-time-tracker)
### [ChatGPT Uptime](https://status.openai.com/uptime)

### References

![attention](https://github.com/JSJeong-me/ProDiscovery2LLM/assets/54794815/200e4d8e-be5c-47fd-b04a-4723d15bd3aa)


[Transformer](https://machinelearningmastery.com/how-to-implement-scaled-dot-product-attention-from-scratch-in-tensorflow-and-keras/)
