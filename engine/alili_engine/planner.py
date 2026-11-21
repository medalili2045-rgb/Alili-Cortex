"""Deterministic task classification. Planning only; no tool execution."""

from dataclasses import dataclass


@dataclass(frozen=True)
class TaskPlan:
    capability_id: str
    title: str
    steps: tuple[str, ...]
    requires_user_approval: bool
    execution_status: str = "not_started"

    def to_dict(self) -> dict:
        return {
            "capability_id": self.capability_id,
            "title": self.title,
            "steps": list(self.steps),
            "requires_user_approval": self.requires_user_approval,
            "execution_status": self.execution_status,
        }


class TaskPlanner:
    _groups = (
        ("document_processing", ("pdf", "docx", "xlsx", "pptx", "csv", "ملف", "مستند", "وثيقة", "جدول", "اكسل", "إكسل")),
        ("research_search", ("ابحث", "بحث", "مصادر", "مراجع", "research", "search", "sources", "latest", "آخر الأخبار")),
        ("software_execution", ("برمج", "كود", "code", "build", "اختبر", "اختبار", "مستودع", "repository", "تطبيق", "app")),
        ("vision_ocr", ("صورة", "صورة", "ocr", "استخرج النص", "حلل الصورة", "image")),
        ("image_audio_video", ("فيديو", "صوت", "موسيقى", "صمم صورة", "أنشئ صورة", "video", "audio", "generate image")),
        ("3d_cad", ("3d", "cad", "blender", "freecad", "مجسم", "تصميم ثلاثي")),
    )

    def plan(self, user_input: str) -> TaskPlan:
        normalized = user_input.casefold()
        capability_id = "task_planning"
        for candidate, keywords in self._groups:
            if any(keyword.casefold() in normalized for keyword in keywords):
                capability_id = candidate
                break

        if capability_id == "task_planning":
            title = "تحليل الطلب وتقسيمه إلى خطوات"
            steps = (
                "تحديد النتيجة المطلوبة والقيود.",
                "تحديد المدخلات والموارد المجانية المتاحة.",
                "اقتراح خطوات قابلة للتحقق قبل التنفيذ.",
                "عرض الخطة للمراجعة قبل أي إجراء ذي أثر خارجي.",
            )
        else:
            title = "إعداد خطة لقدرة: " + capability_id
            steps = (
                "التحقق من توفر محول القدرة وحالته الفعلية.",
                "التحقق من الترخيص والموارد وسياسة المجانية.",
                "التحقق من المدخلات وحدود الحجم والصلاحيات.",
                "تنفيذ اختبارات معزولة عند توفر المحول.",
                "عرض النتائج والأخطاء والمصادر دون ادعاء اكتمال غير مثبت.",
            )

        return TaskPlan(
            capability_id=capability_id,
            title=title,
            steps=steps,
            requires_user_approval=capability_id in {"software_execution", "document_processing", "image_audio_video"},
        )
