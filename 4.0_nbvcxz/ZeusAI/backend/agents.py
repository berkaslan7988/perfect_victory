"""
ZeusAI Faz 11 — Multi-Agent Orkestrasyonu
=================================================
Gerçek ayrı ajan sınıfları: Planner, Coder, Researcher, Validator.
Her birinin kendi system promptu, araç alt-kümesi ve modeli var.
Paralel & sıralı görev yürütme desteği.
"""
import asyncio
import json
from typing import Optional
from dataclasses import dataclass, field

import litellm

from backend.config import WORKSPACE_DIR, route_model_by_complexity
from backend.tools import TOOLS, TOOL_EXECUTORS

# ==========================================
# ARAÇ ALT-KÜMELERİ
# ==========================================
CODE_TOOLS = {
    "create_file", "read_file", "edit_file", "list_files",
    "diff_files", "search_in_files",
    "run_python_code", "run_command",
    "git_status", "git_diff", "git_commit", "git_log",
}

WEB_TOOLS = {
    "browser_navigate", "browser_click", "browser_type", "browser_screenshot",
    "web_search", "http_request",
}

FILE_TOOLS = {
    "create_file", "read_file", "edit_file", "list_files",
    "diff_files", "search_in_files",
}

SYSTEM_TOOLS = {
    "analyze_screen", "list_processes",
    "computer_click", "computer_type", "computer_find_on_screen",
}

VOICE_TOOLS = {"voice_listen", "voice_speak"}
MONITOR_TOOLS = {"start_screen_monitor", "stop_screen_monitor", "check_screen_monitor"}

# ==========================================
# AJAN SINIFLARI
# ==========================================
@dataclass
class TaskStep:
    """Planner'ın çıkardığı bir görev adımı."""
    id: str
    goal: str
    agent: str = "coder"           # planner|coder|researcher|validator
    depends_on: list[str] = field(default_factory=list)  # Önce tamamlanması gereken step id'leri
    result: Optional[str] = None
    status: str = "pending"         # pending|running|done|failed


class BaseAgent:
    """Tüm ajanlar için temel sınıf."""
    name: str = "base"
    icon: str = "⚙️"
    model: str = "deepseek/deepseek-chat"
    tools: set[str] = set()
    system_prompt_extra: str = ""

    def get_system_prompt(self) -> str:
        return f"""Sen ZeusAI'nin {self.name} ajanısın.
{self.system_prompt_extra}

Kullanabileceğin araçlar: {', '.join(sorted(self.tools)) if self.tools else 'TÜM ARAÇLAR'}
SADECE yukarıdaki araçları kullan. Uydurma araç ismi üretme."""

    def get_tools(self) -> list[dict]:
        if not self.tools:
            return TOOLS
        return [t for t in TOOLS if t["function"]["name"] in self.tools]


class PlannerAgent(BaseAgent):
    """Görevi analiz eder, adımlara böler, bağımlılıkları belirler."""
    name = "Planner"
    icon = "🧠"
    model = "deepseek/deepseek-reasoner"
    tools = FILE_TOOLS | {"web_search"}
    system_prompt_extra = (
        "Görevi analiz et. Max 10 adımlık bir plan çıkar. "
        "Her adım için hangi ajanın (coder/researcher) çalışacağını "
        "ve hangi adımlara bağımlı olduğunu belirt. "
        "Bağımsız adımları 'parallel: true' olarak işaretle."
    )

    async def create_plan(self, goal: str) -> list[TaskStep]:
        """LLM ile görev analizi yapıp adım listesi döndürür."""
        messages = [
            {"role": "system", "content": self.get_system_prompt()},
            {"role": "user", "content": (
                f"Bu görevi adımlara böl:\n{goal}\n\n"
                "JSON formatında yanıt ver:\n"
                '{"steps": [{"id": "1", "goal": "...", "agent": "coder|researcher", '
                '"depends_on": [], "parallel": false}]}\n'
                "Bağımsız adımlar için parallel: true yap."
            )}
        ]
        try:
            resp = await asyncio.to_thread(
                litellm.completion,
                model=self.model,
                messages=messages,
                temperature=0.1,
                max_tokens=2000,
            )
            content = resp.choices[0].message.content
            # JSON parse
            data = json.loads(content) if isinstance(content, str) else content
            steps_raw = data.get("steps", [])
            return [
                TaskStep(
                    id=s.get("id", str(i)),
                    goal=s.get("goal", ""),
                    agent=s.get("agent", "coder"),
                    depends_on=s.get("depends_on", []),
                )
                for i, s in enumerate(steps_raw)
            ]
        except Exception:
            # Fallback: basit tek adım
            return [TaskStep(id="1", goal=goal, agent="coder")]


class CoderAgent(BaseAgent):
    """Kod yazar, dosya oluşturur, test eder."""
    name = "Coder"
    icon = "💻"
    model = "deepseek/deepseek-chat"
    tools = CODE_TOOLS
    system_prompt_extra = (
        "Kod yazma ve dosya işlemlerinden sorumlusun. "
        "Her zaman hatasız, çalışan kod üret. Test etmeden bırakma. "
        "Dosya oluşturduktan sonra run_python_code ile test et."
    )


class ResearcherAgent(BaseAgent):
    """Araştırma yapar, web'den bilgi toplar."""
    name = "Researcher"
    icon = "🔍"
    model = "gemini/gemini-2.5-flash"
    tools = WEB_TOOLS | FILE_TOOLS | {"analyze_screen"}
    system_prompt_extra = (
        "Araştırma ve bilgi toplamadan sorumlusun. "
        "Web araması, tarayıcı kullanımı, ekran analizi yapabilirsin. "
        "Bulgularını net ve yapılandırılmış şekilde raporla."
    )


class ValidatorAgent(BaseAgent):
    """Kodu ve sonuçları doğrular, hataları bulur."""
    name = "Validator"
    icon = "✅"
    model = "groq/llama-3.1-8b-instant"
    tools = FILE_TOOLS | {"web_search", "analyze_screen"}
    system_prompt_extra = (
        "Doğrulama ve kalite kontrolden sorumlusun. "
        "Üretilen kodu oku, hataları bul, eksikleri raporla. "
        "Görev hedefiyle sonuçları karşılaştır."
    )


# ==========================================
# ORKESTRATÖR (PARALEL & SIRALI YÜRÜTME)
# ==========================================
@dataclass
class OrchestratorState:
    planner: PlannerAgent = field(default_factory=PlannerAgent)
    coder: CoderAgent = field(default_factory=CoderAgent)
    researcher: ResearcherAgent = field(default_factory=ResearcherAgent)
    validator: ValidatorAgent = field(default_factory=ValidatorAgent)
    current_agent: str = "planner"

    def get_agent(self, name: str) -> BaseAgent:
        return {"planner": self.planner, "coder": self.coder,
                "researcher": self.researcher, "validator": self.validator}[name]


async def execute_plan(
    goal: str,
    ws_send_func=None,
    cancel_event: Optional[asyncio.Event] = None,
) -> list[TaskStep]:
    """
    Planı çıkarır, bağımsız adımları paralel, bağımlıları sıralı çalıştırır.
    Tüm adımların sonucunu döndürür.
    """
    state = OrchestratorState()

    # 1. Planla
    if ws_send_func:
        await ws_send_func("agent_switch", agent="planner", content="Plan oluşturuluyor...")
    steps = await state.planner.create_plan(goal)

    completed: dict[str, TaskStep] = {}

    # 2. Adımları çalıştır — önce bağımsızlar paralel, sonra bağımlılar sıralı
    while len(completed) < len(steps):
        # Çalıştırılmaya hazır adımları bul (tüm bağımlılıkları tamamlanmış)
        ready = [
            s for s in steps
            if s.id not in completed
            and all(dep in completed for dep in s.depends_on)
        ]
        if not ready:
            break  # Döngüsel bağımlılık varsa kır

        # Paralel çalıştırılabilir olanları ayır
        parallel_steps = [s for s in ready]

        async def run_step(step: TaskStep) -> TaskStep:
            if cancel_event and cancel_event.is_set():
                step.status = "failed"
                step.result = "İptal edildi."
                return step

            agent = state.get_agent(step.agent)
            if ws_send_func:
                await ws_send_func("agent_switch", agent=step.agent, content=step.goal)

            step.status = "running"
            try:
                messages = [
                    {"role": "system", "content": agent.get_system_prompt()},
                    {"role": "user", "content": step.goal}
                ]
                resp = await asyncio.to_thread(
                    litellm.completion,
                    model=agent.model,
                    messages=messages,
                    tools=agent.get_tools(),
                    temperature=0.2,
                    max_tokens=1000,
                )
                step.result = resp.choices[0].message.content
                step.status = "done"
            except Exception as e:
                step.result = f"Hata: {str(e)}"
                step.status = "failed"

            return step

        results = await asyncio.gather(*[run_step(s) for s in parallel_steps])
        for s in results:
            completed[s.id] = s

    # 3. Validator ile doğrula
    if ws_send_func:
        await ws_send_func("agent_switch", agent="validator", content="Sonuçlar doğrulanıyor...")
    try:
        all_results = "\n".join(f"[{s.id}] {s.agent}: {s.result or '...'}" for s in steps)
        messages = [
            {"role": "system", "content": state.validator.get_system_prompt()},
            {"role": "user", "content": f"Hedef: {goal}\n\nSonuçlar:\n{all_results}\n\nHedef başarıldı mı? Eksik var mı?"}
        ]
        resp = await asyncio.to_thread(
            litellm.completion,
            model=state.validator.model,
            messages=messages,
            temperature=0.1,
            max_tokens=500,
        )
        # Validation sonucu
        if ws_send_func:
            await ws_send_func("thinking", content=resp.choices[0].message.content)
    except Exception:
        pass

    return steps


# ==========================================
# KULLANILABİLİRLİK KONTROLÜ
# ==========================================
AGENTS_AVAILABLE = True  # Her zaman çalışır (fallback'li)

AGENT_REGISTRY = {
    "planner": PlannerAgent(),
    "coder": CoderAgent(),
    "researcher": ResearcherAgent(),
    "validator": ValidatorAgent(),
}