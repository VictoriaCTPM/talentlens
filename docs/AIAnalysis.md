# AI Analysis Engine — Описание логики

## Обзор

Движок анализа реализован в `backend/app/services/analysis.py` и предоставляет **5 режимов** (A–E), каждый из которых выполняет **1 LLM-вызов** с Pydantic-валидацией результата.

---

## Архитектура: путь запроса

```
HTTP POST /api/analysis/<mode>
    │
    ├─ 1. Проверка документа (processed?)
    ├─ 2. Data Sufficiency Check (достаточно данных?)
    │
    ├─ 3. AnalysisEngine.<mode>(document_id)
    │       ├─ _load_extracted()       → структурированные данные документа из БД
    │       ├─ RetrievalService        → гибридный поиск (BM25 + vector) по проекту
    │       ├─ TeamContextService      → текущий состав команды + отчёты
    │       │
    │       ├─ Сборка промпта (JD + контекст + команда + GROUNDING rules)
    │       ├─ _call_with_validation() → LLM → JSON → Pydantic (до 2 попыток)
    │       └─ _save_and_return()      → сохранение в AnalysisResult + ответ
    │
    └─ JSON response → фронтенд
```

---

## Режимы анализа

### Режим A — Talent Brief

**Эндпоинт:** `POST /api/analysis/talent-brief`
**Входные данные:** `document_id` (тип: JD или job_request)
**Необходимый минимум:** 1 JD

**Что делает:**
По описанию вакансии (JD) формирует рекрутинговый бриф: какие навыки искать, советы по поиску, исторические инсайты, типичные ошибки и оценку срока закрытия.

**Контекст для LLM:**
- Структурированные данные JD (title, required_skills и т.д.)
- Исторические документы: JD, job_request, report, interview (top-5000 токенов)
- Состав команды (TeamContextService)

**Логика работы с командой:**
Навыки из JD, которые уже есть у членов команды → `criticality: "nice"`.
Навыки, которых нет в команде → `criticality: "must"`.
Поисковые советы адаптируются под текущий состав (например: "Python в команде уже есть, ищи Kubernetes").

**Структура ответа:**
```json
{
  "skills_required": [{"name": "...", "criticality": "must|nice", "market_availability": "easy|moderate|hard"}],
  "search_guidance": ["..."],
  "historical_insights": ["... [Source N]"],
  "pitfalls": ["..."],
  "estimated_time_to_fill_days": 30,
  "confidence": 0.75,
  "confidence_level": "HIGH|MEDIUM|LOW",
  "key_arguments": [{"point": "...", "evidence": "...", "impact": "positive|negative|neutral"}],
  "reasoning": "3-5 предложений..."
}
```

---

### Режим B — Historical Match

**Эндпоинт:** `POST /api/analysis/historical-match`
**Входные данные:** `document_id` (JD)
**Необходимый минимум:** 1 JD; рекомендуется 5+ исторических документов

**Что делает:**
Находит похожие позиции из прошлых проектов и извлекает паттерны успехов и неудач.

**Контекст для LLM:**
- Данные JD
- Все типы документов из проекта (report, resume, interview и т.д.) — top-6000 токенов
- Состав команды

**Структура ответа:**
```json
{
  "similar_positions": [{"project": "...", "role": "...", "outcome": "...", "time_to_fill": 45, "key_learnings": "... [Source N]"}],
  "success_patterns": ["..."],
  "failure_patterns": ["..."],
  "confidence": 0.6,
  "reasoning": "..."
}
```

---

### Режим C — Level Advisor

**Эндпоинт:** `POST /api/analysis/level-advisor`
**Входные данные:** `document_id` (JD)
**Необходимый минимум:** 1 JD; для высокого качества — 2+ отчёта

**Что делает:**
Рекомендует уровень сениорности для найма (junior / mid / senior / lead) на основе исторических данных и текущего состава команды.

**Логика:**
Если в текущей команде нет технических лидеров — рекомендует senior/lead.
Если команда уже из сеньоров — может порекомендовать mid как индивидуального контрибьютора.

**Структура ответа:**
```json
{
  "recommended_level": "mid",
  "reasoning": "...",
  "evidence": [{"project": "...", "role": "...", "level": "senior", "outcome": "..."}],
  "risk_of_wrong_level": "...",
  "confidence": 0.7
}
```

---

### Режим D — Candidate Scorer

**Эндпоинт:** `POST /api/analysis/candidate-score`
**Входные данные:** `resume_document_id` + `jd_document_id`
**Необходимый минимум:** 1 резюме + 1 JD

**Что делает:**
Оценивает кандидата (резюме) относительно вакансии (JD). Выдаёт итоговый балл 0–100, вердикт и детальный разбор.

**Контекст для LLM:**
- Данные резюме (structured_data)
- Данные JD
- Исторические похожие кандидаты: resume, interview, report — top-5000 токенов
- Состав команды (для оценки комплементарности)

**Логика оценки:**
Кандидат, закрывающий реальные пробелы команды → балл повышается.
Кандидат, дублирующий уже существующие в команде навыки → балл снижается.

**Вердикты по баллу:**
| Балл | Вердикт |
|------|---------|
| 85–100 | `strong_fit` |
| 65–84 | `moderate_fit` |
| 45–64 | `risky` |
| < 45 | `not_recommended` |

**Структура ответа:**
```json
{
  "overall_score": 72,
  "verdict": "moderate_fit",
  "skill_match": {"score": 80, "matched": [...], "missing": [...], "partial": [...]},
  "experience_match": {"score": 75, "relevant_years": 5, "notes": "..."},
  "team_compatibility": {"score": 70, "notes": "..."},
  "team_complementarity": {
    "score": 75,
    "fills_gaps": ["навыки, которых нет в команде"],
    "overlaps": ["навыки, которые уже есть в команде"],
    "team_dynamics": "...",
    "recommendation": "..."
  },
  "strengths": [...],
  "gaps": [...],
  "historical_comparison": {"similar_hire": "...", "project": "...", "outcome": "..."},
  "reasoning": "..."
}
```

---

### Режим E — JD Reality Check

**Эндпоинт:** `POST /api/analysis/jd-reality-check`
**Входные данные:** `document_id` (JD)
**Необходимый минимум:** 1 JD; для высокого качества — 2+ отчёта

**Что делает:**
Аудит JD: насколько требования соответствуют реальности проекта и действительно ли нужен этот найм.

**Контекст для LLM (самый широкий):**
- Данные JD
- Состав команды + навыки (TeamContextService)
- Еженедельные отчёты — что команда реально делает (get_reports_context)
- Дополнительные документы: report, client_report, resume, interview

**Три ключевых проверки:**
1. **Skills vs Reality** — требуют ли в JD навыки, которые в команде уже есть? Есть ли в JD требования, не соответствующие фактической работе?
2. **Workload Analysis** — что JD говорит о роли vs что команда реально делает по отчётам.
3. **Necessity Check** — обоснован ли найм? Есть ли альтернативы (обучить существующего члена, перераспределить задачи)?

**Структура ответа:**
```json
{
  "skills_vs_reality": {
    "jd_requires": [...],
    "team_already_has": [...],
    "actually_needed": [...],
    "questionable_requirements": [...]
  },
  "workload_analysis": {
    "jd_claims": "...",
    "report_reality": "...",
    "mismatches": [...],
    "is_jd_accurate": true
  },
  "necessity_check": {
    "is_hire_justified": true,
    "reasoning": "...",
    "alternative_suggestions": [...],
    "priority": "critical|high|medium|low"
  },
  "jd_improvement_suggestions": [...]
}
```

---

## Система проверки данных (Data Sufficiency Check)

Перед запуском анализа выполняется проверка наличия необходимых документов в проекте.

**Эндпоинт:** `GET /api/analysis/sufficiency/{project_id}/{mode}`

Подсчитываются документы по типам: `jd`, `job_request`, `resume`, `report`, `client_report`, `interview`.

| Режим | Минимум | Качество HIGH |
|-------|---------|---------------|
| A | 1 JD | 2+ отчёта или 5+ документов |
| B | 1 JD | 6+ документов |
| C | 1 JD | 3+ отчёта |
| D | 1 JD + 1 резюме | 2+ отчёта + 1 интервью |
| E | 1 JD | 2+ отчёта |

Если данных недостаточно — API возвращает `422` с описанием того, чего не хватает.

---

## Гибридный поиск контекста (RetrievalService)

Перед каждым LLM-вызовом движок выполняет поиск по документам проекта.

**Механизм: BM25 + Vector + RRF**

```
1. BM25 (ключевые слова) → ранжирование по TF-IDF
2. Vector search (семантика) → косинусное сходство через ChromaDB
3. Reciprocal Rank Fusion (k=60) → объединение двух списков по формуле:
   RRF_score = 1/(k + rank_BM25) + 1/(k + rank_vector)
4. Результат: top-N чанков, отсортированных по combined_score
5. Сборка контекста с метками [Source 1], [Source 2], ...
```

**Фильтрация:** по `project_id` и `doc_type` через метаданные ChromaDB.
**Лимит токенов:** настраивается на уровне режима (5000–6000 токенов).

---

## Контекст команды (TeamContextService)

Инжектируется во все 5 режимов. Строится динамически из БД при каждом запросе.

**get_team_context()** — возвращает строку вида:
```
## Current Project Team (4 active members)

### Backend Developer (2):
- Иван Петров, Senior Backend Developer (since Jan 2025)
  Skills: Python, FastAPI, PostgreSQL, Redis
  Recent work: Migrate auth service to JWT

### Team Skill Summary:
Strong in: Python (3), PostgreSQL (2), React (2), ...

### Team Observations from Reports:
- 2 candidate(s) placed across recent reports
- Blocker: Client delayed feedback on CVs
```

**get_reports_context()** — краткая сводка еженедельных отчётов:
Автор, кол-во поданных/принятых кандидатов, блокеры, следующие шаги. Используется в режиме E.

---

## Анти-галлюцинационная система

В каждый промпт инжектируются **5 правил** (`_GROUNDING`):

1. Анализ только по предоставленным документам — без выдуманных фактов
2. Обязательные ссылки `[Source N]` для каждого утверждения
3. Явное указание на нехватку данных — без домыслов
4. Оценка уверенности: LOW / MEDIUM / HIGH
5. Ответ только валидным JSON — никакого markdown вне JSON

---

## Валидация и повторные попытки

```python
for attempt in range(2):
    response = await llm.generate(prompt, temperature=0.1, max_tokens=2048)
    try:
        raw = _parse_json(response)          # удаляет ```json фенсы
        validated = SchemaClass(**raw)        # Pydantic-валидация
        return validated.model_dump()
    except (ValidationError, JSONDecodeError):
        if attempt == 0:
            # Добавляем ошибку в промпт и пробуем снова
            prompt += f"\n\nPREVIOUS ATTEMPT FAILED: {error}\nFix and return valid JSON."
        else:
            raise ValueError("Analysis failed after 2 attempts")
```

`temperature=0.1` — минимальная температура для максимальной детерминированности JSON.

---

## Хранение результатов

Каждый результат сохраняется в таблице `AnalysisResult`:

| Поле | Описание |
|------|----------|
| `project_id` | ID проекта |
| `analysis_mode` | A / B / C / D / E |
| `input_document_ids` | ID входных документов |
| `result_data` | Полный JSON результата |
| `confidence_score` | Числовая уверенность (0–1) |
| `source_citations` | Список источников |
| `model_used` | Название LLM-модели |
| `prompt_version` | Версия промпта (сейчас: 1.0) |

**Чтение истории:** `GET /api/analysis/results/{project_id}` — все результаты проекта, свежие первыми.

---

## Схема зависимостей

```
AnalysisEngine
    ├── LLMProvider (Groq / OpenAI / Mock)
    ├── RetrievalService
    │       ├── BM25Okapi
    │       ├── EmbeddingService (sentence-transformers)
    │       └── VectorStore (ChromaDB)
    └── TeamContextService
            └── SQLAlchemy (TeamMember, Document, ExtractedData)
```
