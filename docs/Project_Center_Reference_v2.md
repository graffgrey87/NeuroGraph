База знаний проекта NeuroGraph (v8.0)
Сохраните этот текст как основной контекстный файл бота.
📂 АКТУАЛЬНАЯ АРХИТЕКТУРА (v8.0 Stable)
Стек: Python aiogram + ComfyUI API (Port 3000).  
Ядро генерации: Flux 2 Klein (9B).  
Редактирование: Qwen Image Edit (Node 126).  
🛠 КЛЮЧЕВЫЕ ФАЙЛЫ И ПУТИ
Исполняемый файл: /workspace/bot.py (v8.0 с поддержкой WebApp).  
Воркфлоу Flux: /workspace/TI2I_Flux2_Klein.json (Исправленная версия v8.0).  
Воркфлоу Qwen: /workspace/workflow_api.json (Режим редактирования).  
Лоры: * Общие: /workspace/ComfyUI/models/loras/
Qwen-специфичные: /workspace/ComfyUI/models/loras/qwen/ (только .safetensors).  
🧩 ID КРИТИЧЕСКИХ НОД (ДЛЯ ПОИСКА В JSON)
Seed Control: IDs 117, 122 (Flux), 205 (Qwen).
Lora Loader: Power Lora Loader (rgthree) — IDs 153 (Flux), 206 (Qwen).
Camera Unit (Flux):
Rotation (ID 149): 0-Off, 1-Front, 2-3/4, 3-Side, 4-Rear.  
Angle (ID 143): High, Straight, Low.  
Distance (ID 150): Close up, Half-body, Full-body.  
⚠️ ИСПРАВЛЕННЫЕ БАГИ И РЕШЕНИЯ
Ошибка 400 (Missing Node): Ноды 175, 194, 222, 223 в TI2I_Flux2_Klein.json восстановлены с корректными типами.  
Ошибка 500 (Resolution): Внедрен RES_MAP для перевода значений WebApp (напр. 1024x1024) в формат ноды (1:1).  
Исчезновение меню: К каждому сообщению бота принудительно прикрепляется reply_markup.