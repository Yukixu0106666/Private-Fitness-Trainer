const $ = (id) => document.getElementById(id);
const height = 158;
const today = new Date();
const isoDate = (date) => {
  const local = new Date(date.getTime() - date.getTimezoneOffset() * 60000);
  return local.toISOString().slice(0, 10);
};

let photos = [];
let records = [];
let profile = {};
let registerMode = false;
let activePhase = today.getHours() < 11 ? "morning" : today.getHours() < 18 ? "midday" : "evening";
let language = localStorage.getItem("fitness-coach-language") || "zh";

const enText = {
  "我的健身教练": "My Fitness Coach", "记录今天，获得更适合明天的训练建议。": "Log today and get guidance for a better tomorrow.",
  "退出登录": "Log out", "登录": "Log in", "注册": "Sign up", "邮箱": "Email", "密码（至少 8 位）": "Password (at least 8 characters)",
  "还没有账号？注册": "No account yet? Sign up", "已有账号？登录": "Already have an account? Log in", "注册并登录": "Sign up and log in",
  "今天的教练": "Today's coach", "早": "AM", "中": "MID", "晚": "PM", "早上计划": "Morning plan", "状态与今日安排": "Status and daily plan",
  "训练完成": "Workout done", "运动与拉伸": "Exercise and stretching", "晚上复盘": "Evening review", "饮食与排便": "Food and digestion",
  "早上好，先看看今天的身体状态": "Good morning — let's check how your body feels", "你的目标": "Your goal", "减脂塑形": "Fat loss & shaping",
  "增肌增力": "Build muscle & strength", "提升体能": "Improve fitness", "保持健康": "Stay healthy", "晨起体重（kg）": "Morning weight (kg)",
  "睡眠（小时）": "Sleep (hours)", "建议晨起、如厕、早餐前称重，趋势更有参考价值。": "For a useful trend, weigh after using the bathroom and before breakfast.",
  "精力": "Energy", "肌肉酸痛": "Muscle soreness", "可运动时间": "Time available", "身体不适或特别安排": "Pain or special considerations",
  "可选": "Optional", "生成今天的饮食与运动计划": "Create today's meal and workout plan", "练完了，记录实际完成情况": "Workout complete — log what you actually did",
  "做了哪些运动，各做了多少？": "Which exercises did you do, and how much?", "＋ 添加一项运动": "+ Add exercise",
  "是否按早上建议完成": "Followed the morning plan?", "全部完成": "Completed all", "完成一部分": "Completed part", "做了其他运动": "Did a different workout",
  "今天没做": "No workout today", "实际强度": "Perceived effort", "训练后感觉": "How did you feel afterward?", "生成训练后拉伸建议": "Create post-workout stretches",
  "晚上好，完成今天的饮食与身体复盘": "Good evening — finish today's food and body review", "今天一整天吃了什么？": "What did you eat today?",
  "饮食照片": "Food photos", "可上传餐食照片帮助 AI 判断搭配": "Upload meal photos to help AI review food balance", "一整天排便情况": "Bowel movements today",
  "帮助教练调整纤维和饮水": "Helps adjust fiber and hydration", "次数": "Count", "没有": "None", "1 次": "Once", "2 次": "Twice", "3 次或以上": "3 or more",
  "状态": "Consistency", "正常": "Normal", "偏硬/干结": "Hard / dry", "偏稀": "Loose", "水样": "Watery", "不确定": "Not sure", "感受": "Symptoms",
  "无明显不适": "No discomfort", "需要用力": "Straining", "没排干净": "Incomplete", "伴随腹胀": "Bloating", "疼痛/出血": "Pain / bleeding",
  "持续疼痛、出血或明显异常请咨询医生。": "Consult a doctor for persistent pain, bleeding, or unusual symptoms.", "今晚还有什么感受？": "Anything else tonight?",
  "完成今日复盘": "Complete today's review", "照片会发送到你配置的 AI 服务分析，请勿上传敏感或可识别他人的照片。": "Photos are sent to your configured AI service. Do not upload sensitive or identifying images.",
  "今日教练": "Today's coach", "清空": "Clear", "从早上的状态开始": "Start with your morning check-in", "我会陪你完成早上计划、训练后拉伸和晚上复盘，并在明早为今天评分。": "I'll guide your morning plan, post-workout stretch, and evening review, then score today tomorrow morning.",
  "最近记录": "Recent records", "0 条记录": "0 records", "完成第一次打卡后，这里会显示你的记录。": "Your records will appear after your first check-in.",
  "健康建议不能替代医生或持证教练的诊断。出现疼痛、胸闷、眩晕等症状时请停止训练并寻求专业帮助。": "Health guidance does not replace a doctor or certified trainer. Stop and seek help for pain, chest tightness, or dizziness.",
  "很好": "Very good", "不错": "Good", "一般": "Average", "较低": "Low", "很差": "Very low", "几乎没有": "Almost none", "轻微": "Slight", "中等": "Moderate", "明显": "Noticeable", "很严重": "Severe",
  "很轻松": "Very easy", "适中": "Moderate", "较累": "Hard", "非常累": "Very hard", "分钟": "min", "个": "reps", "已保存": "Saved",
  "长期记忆设置": "Long-term memory", "由你确认后保存": "saved only after your confirmation", "可用器械": "Available equipment", "饮食偏好或限制": "Dietary preferences or restrictions", "长期身体限制": "Long-term physical constraints", "只填写希望教练长期记住的信息": "Only enter information you want the coach to remember"
};
const originalText = new WeakMap();
const originalPlaceholder = new WeakMap();
const tr = (text) => language === "en" ? (enText[text] || text) : text;

function applyLanguage() {
  document.documentElement.lang = language === "en" ? "en" : "zh-CN";
  document.title = tr("我的健身教练");
  const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  let node;
  while ((node = walker.nextNode())) {
    if (!originalText.has(node)) originalText.set(node, node.nodeValue);
    const original = originalText.get(node);
    const trimmed = original.trim();
    node.nodeValue = trimmed ? original.replace(trimmed, tr(trimmed)) : original;
  }
  document.querySelectorAll("[placeholder]").forEach((element) => {
    if (!originalPlaceholder.has(element)) originalPlaceholder.set(element, element.placeholder);
    const original = originalPlaceholder.get(element);
    element.placeholder = language === "en" ? ({
      "例如：55.05": "e.g. 55.05", "运动名称，如快走": "Exercise, e.g. brisk walking", "例如：右膝不舒服，今天只能在家练": "e.g. My right knee hurts; I can only train at home",
      "例如：腿比较紧，左肩活动时不舒服": "e.g. Tight legs and left shoulder discomfort", "按早餐、午餐、晚餐和加餐记录，尽量写上大致分量": "List breakfast, lunch, dinner, snacks, and approximate portions",
      "例如：晚饭后很撑、今天喝水比较少": "e.g. Felt too full after dinner and drank little water", "例如：瑜伽垫、哑铃、弹力带": "e.g. yoga mat, dumbbells, resistance bands", "例如：不吃牛肉、乳糖不耐": "e.g. no beef, lactose intolerant", "只填写希望教练长期记住的信息": "Only enter information you want the coach to remember"
    }[original] || original) : original;
  });
  $("language-toggle").textContent = language === "en" ? "中文" : "English";
}

$("log-date").value = isoDate(today);

function escapeHtml(value) {
  return String(value ?? "").replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;").replaceAll('"', "&quot;").replaceAll("'", "&#039;");
}

function priorDate(dateString) {
  const date = new Date(`${dateString}T12:00:00`);
  if (Number.isNaN(date.getTime())) return "";
  date.setDate(date.getDate() - 1);
  return isoDate(date);
}

function currentRecord() {
  return records.find((record) => record.date === $("log-date").value) || null;
}

function setValue(id, value, fallback = "") { $(id).value = value ?? fallback; }

function addExerciseRow(name = "", amount = "", unit = "minutes") {
  const row = document.createElement("div");
  row.className = "exercise-row";
  row.innerHTML = `<input class="exercise-name" type="text" placeholder="运动名称，如快走" value="${escapeHtml(name)}" /><div class="exercise-measure"><input class="exercise-amount" type="number" min="0" max="10000" step="1" placeholder="30" value="${escapeHtml(amount)}" /><select class="exercise-unit" aria-label="单位"><option value="minutes"${unit === "minutes" ? " selected" : ""}>分钟</option><option value="reps"${unit === "reps" ? " selected" : ""}>个</option></select></div><button class="remove-exercise" type="button" aria-label="删除这项运动">×</button>`;
  row.querySelector(".remove-exercise").addEventListener("click", () => {
    row.remove();
    if (!$("exercise-list").children.length) {
      addExerciseRow();
      applyLanguage();
    }
  });
  $("exercise-list").appendChild(row);
}

$("add-exercise").addEventListener("click", () => {
  addExerciseRow();
  applyLanguage();
});

function showApp(user) {
  $("auth-card").classList.toggle("hidden", !!user);
  $("app-content").classList.toggle("hidden", !user);
  $("history-content").classList.toggle("hidden", !user);
  $("app-footer").classList.toggle("hidden", !user);
  $("logout-button").classList.toggle("hidden", !user);
  if (user) $("auth-user").textContent = user.email;
}

async function authRequest(path, body) {
  const response = await fetch(path, { method: "POST", headers: { "Content-Type": "application/json" }, credentials: "same-origin", body: JSON.stringify(body) });
  const result = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(result.error || (language === "en" ? "Action failed" : "操作失败"));
  return result;
}

$("auth-toggle").addEventListener("click", () => {
  registerMode = !registerMode;
  $("auth-title").textContent = tr(registerMode ? "注册" : "登录");
  $("auth-submit").textContent = tr(registerMode ? "注册并登录" : "登录");
  $("auth-toggle").textContent = tr(registerMode ? "已有账号？登录" : "还没有账号？注册");
  $("auth-password").autocomplete = registerMode ? "new-password" : "current-password";
  $("auth-error").textContent = "";
});

$("auth-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  $("auth-error").textContent = "";
  try {
    const result = await authRequest(registerMode ? "/api/register" : "/api/login", { email: $("auth-email").value, password: $("auth-password").value });
    showApp(result.user);
    await loadRecords();
  } catch (error) { $("auth-error").textContent = error.message; }
});

$("logout-button").addEventListener("click", async () => {
  await authRequest("/api/logout", {});
  records = [];
  profile = {};
  renderHistory();
  showApp(null);
});

function switchPhase(phase, showSavedResponse = true) {
  activePhase = phase;
  document.querySelectorAll(".phase-tab").forEach((tab) => tab.classList.toggle("active", tab.dataset.phase === phase));
  ["morning", "midday", "evening"].forEach((name) => $(`${name}-form`).classList.toggle("hidden", name !== phase));
  if (showSavedResponse) renderSavedResponse();
}

document.querySelectorAll(".phase-tab").forEach((tab) => tab.addEventListener("click", () => switchPhase(tab.dataset.phase)));

$("language-toggle").addEventListener("click", () => {
  language = language === "zh" ? "en" : "zh";
  localStorage.setItem("fitness-coach-language", language);
  applyLanguage();
  renderHistory();
  renderSavedResponse();
});

$("food-photos").addEventListener("change", (event) => {
  photos = Array.from(event.target.files || []);
  $("photo-preview").innerHTML = photos.length ? photos.map((photo) => `<img src="${URL.createObjectURL(photo)}" alt="饮食照片" />`).join("") : '<div class="upload-hint">可上传餐食照片帮助 AI 判断搭配</div>';
});

const fileToDataUrl = (file) => new Promise((resolve, reject) => {
  const reader = new FileReader();
  reader.onload = () => resolve(reader.result);
  reader.onerror = () => reject(new Error(`${language === "en" ? "Could not read image: " : "无法读取照片："}${file.name}`));
  reader.readAsDataURL(file);
});

function list(items) {
  return Array.isArray(items) && items.length ? `<ul>${items.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul>` : "";
}

function renderCoachResponse(response, phase) {
  if (!response) return showEmptyCoach();
  $("empty-plan").classList.add("hidden");
  $("plan-content").classList.remove("hidden");
  $("plan-title").textContent = response.title || (phase === "morning" ? "今日计划" : phase === "midday" ? "拉伸建议" : "今日复盘");
  if (phase === "morning") {
    const evaluation = response.previousDayEvaluation;
    const hasScore = evaluation && evaluation.score !== null && evaluation.score !== "" && Number.isFinite(Number(evaluation.score));
    const score = hasScore ? `<div class="score-card"><div class="score-number">${escapeHtml(evaluation.score)}<small>/100</small></div><div><strong>昨天表现</strong><p>${escapeHtml(evaluation.summary)}</p></div></div>` : "";
    const meals = response.meals || {};
    $("plan-content").innerHTML = `${score}<div class="plan-intro"><strong>${escapeHtml(response.title)}</strong><br />${escapeHtml(response.summary)}</div>
      <div class="plan-section"><span class="tag">${escapeHtml(response.training?.loadLabel || "今日训练")}</span><h3>今天的运动</h3>${list(response.training?.items)}</div>
      <div class="plan-section"><h3>今天怎么吃</h3><div class="meal-grid"><p><strong>早餐</strong>${escapeHtml(meals.breakfast || "均衡早餐")}</p><p><strong>午餐</strong>${escapeHtml(meals.lunch || "均衡午餐")}</p><p><strong>晚餐</strong>${escapeHtml(meals.dinner || "均衡晚餐")}</p></div>${meals.principles ? `<p>${escapeHtml(meals.principles)}</p>` : ""}</div>
      <div class="plan-section"><h3>恢复提醒</h3><p>${escapeHtml(response.recovery || "根据身体感受调整强度。")}</p></div>`;
  } else if (phase === "midday") {
    $("plan-content").innerHTML = `<div class="plan-intro"><strong>${escapeHtml(response.title)}</strong><br />${escapeHtml(response.summary)}</div><div class="plan-section"><span class="tag">${escapeHtml(response.stretch?.duration || "8–12 分钟")}</span><h3>现在这样拉伸</h3>${list(response.stretch?.items)}</div><div class="plan-section"><h3>安全提醒</h3><p>${escapeHtml(response.stretch?.safety || "拉伸保持轻柔，不要追求疼痛感。")}</p></div>`;
  } else {
    $("plan-content").innerHTML = `<div class="plan-intro"><strong>${escapeHtml(response.title)}</strong><br />${escapeHtml(response.summary)}</div><div class="plan-section"><h3>今天做得好的地方</h3>${list(response.wins)}</div><div class="plan-section"><h3>明早评分会关注</h3>${list(response.tomorrowScoreFactors)}</div><div class="plan-section"><h3>今晚提醒</h3><p>${escapeHtml(response.tonightTip || "早点休息并适量补水。")}</p></div>`;
  }
  applyLanguage();
}

function renderProvenance(provenance) {
  const element = $("plan-provenance");
  if (!provenance || !Array.isArray(provenance.sources)) {
    element.classList.add("hidden");
    element.innerHTML = "";
    return;
  }
  const sourceLabels = provenance.sources.map((source) => {
    if (source.type === "confirmed_profile") return language === "en" ? "confirmed profile" : "已确认画像";
    if (source.type === "daily_record") return `${language === "en" ? "record" : "记录"} ${source.date}`;
    if (source.type === "coach_output") return `${language === "en" ? "prior AI plan" : "既有 AI 计划"} ${source.date}`;
    if (source.type === "server_derived_stats") return `${language === "en" ? "server-calculated trend" : "服务端计算趋势"} ${source.period?.from || ""}–${source.period?.to || ""}`;
    if (source.type === "tool_daily_record") return `${language === "en" ? "extra record" : "补充记录"} ${source.date}`;
    if (source.type === "tool_recent_records") return language === "en" ? "extra recent records" : "补充近期记录";
    if (source.type === "tool_derived_weight_trend") return language === "en" ? "extra weight trend" : "补充体重趋势";
    return source.type;
  });
  const missing = Array.isArray(provenance.missingData) && provenance.missingData.length
    ? ` · ${language === "en" ? "Missing" : "缺少"}: ${provenance.missingData.map(escapeHtml).join(", ")}` : "";
  element.innerHTML = `<strong>${language === "en" ? "Evidence" : "依据来源"}</strong>: ${sourceLabels.map(escapeHtml).join(" · ") || (language === "en" ? "current input only" : "仅本次输入")}${missing}`;
  element.classList.remove("hidden");
}

function showEmptyCoach() {
  $("empty-plan").classList.remove("hidden");
  $("plan-content").classList.add("hidden");
  $("plan-content").innerHTML = "";
  $("plan-title").textContent = activePhase === "morning" ? "今日计划" : activePhase === "midday" ? "拉伸建议" : "今日复盘";
  renderProvenance(null);
  applyLanguage();
}

function renderSavedResponse() {
  const record = currentRecord();
  const response = activePhase === "morning" ? record?.plan : activePhase === "midday" ? record?.stretch : record?.eveningReview;
  renderCoachResponse(response, activePhase);
  renderProvenance(record?.coachMetadata?.[activePhase]);
}

function populateForms() {
  const record = currentRecord() || {};
  const morning = record.morning || record;
  const midday = record.midday || record;
  const evening = record.evening || record;
  setValue("goal", record.goal, profile.goal || "fat-loss"); setValue("weight", morning.weight); setValue("sleep", morning.sleep, "7");
  setValue("profile-equipment", profile.equipment); setValue("profile-diet", profile.dietaryPreferences); setValue("profile-constraints", profile.constraints);
  setValue("energy", morning.energy, "3"); setValue("soreness", morning.soreness, "2"); setValue("available-time", morning.availableTime, "45"); setValue("morning-notes", morning.notes);
  $("exercise-list").innerHTML = "";
  const exercises = Array.isArray(midday.exercises) && midday.exercises.length ? midday.exercises : midday.workout ? [{ name: midday.workout, duration: midday.duration || "" }] : [{ name: "", duration: "" }];
  exercises.forEach((exercise) => addExerciseRow(exercise.name, exercise.amount ?? exercise.duration, exercise.unit || "minutes"));
  setValue("plan-adherence", midday.planAdherence, "partial"); setValue("workout-effort", midday.effort, "3"); setValue("workout-notes", midday.notes);
  setValue("food", evening.food); setValue("bowel-frequency", evening.bowelFrequency, "1"); setValue("bowel-form", evening.bowelForm, "normal"); setValue("bowel-symptoms", evening.bowelSymptoms, "none"); setValue("evening-notes", evening.notes);
  $("morning-saved").textContent = record.morning || record.weight ? "✓ 已保存" : "";
  $("midday-saved").textContent = record.midday ? "✓ 已保存" : "";
  $("evening-saved").textContent = record.evening ? "✓ 已保存" : "";
  renderSavedResponse();
  applyLanguage();
}

function renderHistory() {
  $("record-count").textContent = `${records.length} 天记录`;
  $("history-list").innerHTML = records.length ? records.slice(0, 14).map((record) => {
    const nextRecord = records.find((item) => priorDate(item.date) === record.date);
    const score = nextRecord?.plan?.previousDayEvaluation?.score;
    const morning = record.morning || record;
    const phases = [record.morning || record.weight, record.midday, record.evening].filter(Boolean).length;
    return `<div class="history-item"><div class="history-date">${escapeHtml(record.date)}</div><div class="history-summary">${morning.weight ? `${escapeHtml(morning.weight)} kg · ` : ""}${phases}/3 阶段已记录${score !== undefined ? ` · 次日评分 ${escapeHtml(score)}/100` : " · 等待次日评分"}</div></div>`;
  }).join("") : '<p class="muted">完成第一次早间打卡后，这里会显示你的记录。</p>';
  applyLanguage();
}

function setStatus(text, state = "") {
  $("connection-status").className = `status-pill ${state}`;
  $("connection-status").innerHTML = `<span></span> ${escapeHtml(text)}`;
}

async function requestCoach(checkIn, imageData = []) {
  const response = await fetch("/api/coach", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ checkIn, images: imageData, language }) });
  const result = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(result.error || (language === "en" ? "AI coach is temporarily unavailable" : "AI 教练暂时无法响应"));
  return result;
}

async function saveRecord(record) {
  const response = await fetch("/api/records", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(record) });
  const result = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(result.error || (language === "en" ? "Could not save record" : "无法保存记录"));
  profile = result.profile?.confirmed || profile;
  records = [record, ...records.filter((item) => item.date !== record.date)].sort((a, b) => b.date.localeCompare(a.date));
  renderHistory(); populateForms();
}

async function loadRecords() {
  const response = await fetch("/api/records", { credentials: "same-origin" });
  const result = await response.json().catch(() => ({}));
  if (response.status === 401) return;
  if (!response.ok) throw new Error(result.error || (language === "en" ? "Could not load records" : "无法读取历史记录"));
  records = Array.isArray(result.records) ? result.records : [];
  profile = result.profile?.confirmed || {};
  renderHistory(); populateForms();
}

async function runPhase({ phase, button, checkIn, images = [] }) {
  const original = button.innerHTML;
  const factualCheckIn = { ...checkIn };
  const profileUpdate = factualCheckIn.profileUpdate;
  delete factualCheckIn.profileUpdate;
  const existing = currentRecord() || { date: $("log-date").value, height };
  const record = { ...existing, date: $("log-date").value, height, goal: $("goal").value };
  record._invalidatePhase = phase;
  if (phase === "morning") { Object.assign(record, { morning: factualCheckIn, _profile: profileUpdate }); delete record.plan; }
  if (phase === "midday") { Object.assign(record, { midday: factualCheckIn }); delete record.stretch; }
  if (phase === "evening") { Object.assign(record, { evening: factualCheckIn }); delete record.eveningReview; }
  let checkInSaved = false;
  button.disabled = true; button.textContent = language === "en" ? "AI coach is analyzing…" : "AI 教练正在分析…"; setStatus(language === "en" ? "Saving check-in…" : "正在保存打卡…", "loading");
  try {
    await saveRecord(record);
    checkInSaved = true;
    delete record._profile;
    delete record._invalidatePhase;
    setStatus(language === "en" ? "Check-in saved · AI analyzing…" : "打卡已保存 · AI 分析中…", "loading");
    const result = await requestCoach({ phase, ...factualCheckIn }, images);
    const response = result.plan;
    if (phase === "morning") Object.assign(record, { plan: response });
    if (phase === "midday") Object.assign(record, { stretch: response });
    if (phase === "evening") Object.assign(record, { eveningReview: response });
    await loadRecords();
    const usedTools = Array.isArray(result.toolsUsed) && result.toolsUsed.length;
    const forcedFinish = result.agent?.forcedFinish;
    renderCoachResponse(response, phase); renderProvenance(result.provenance); setStatus(language === "en" ? `AI Coach · ${forcedFinish ? "Limited-data fallback" : usedTools ? "Extra history read" : "Fixed memory loaded"}` : `AI 教练 · ${forcedFinish ? "已降级生成" : usedTools ? "已补充读取历史" : "固定记忆已加载"}`);
  } catch (error) {
    setStatus(language === "en" ? "AI service unavailable" : "AI 服务未连接", "error"); $("empty-plan").classList.add("hidden"); $("plan-content").classList.remove("hidden");
    const title = checkInSaved ? (language === "en" ? "Check-in saved, but AI guidance failed" : "打卡已保存，但 AI 建议生成失败") : (language === "en" ? "This check-in was not saved" : "这次没有保存");
    $("plan-content").innerHTML = `<div class="plan-intro"><strong>${escapeHtml(title)}</strong><br />${escapeHtml(error.message)}</div>`;
  } finally { button.disabled = false; button.innerHTML = original; }
}

$("morning-form").addEventListener("submit", (event) => {
  event.preventDefault();
  runPhase({ phase: "morning", button: $("morning-submit"), checkIn: { date: $("log-date").value, goal: $("goal").value, height, weight: $("weight").value, sleep: $("sleep").value, energy: $("energy").value, soreness: $("soreness").value, availableTime: $("available-time").value, notes: $("morning-notes").value.trim(), profileUpdate: { equipment: $("profile-equipment").value.trim(), dietaryPreferences: $("profile-diet").value.trim(), constraints: $("profile-constraints").value.trim() } } });
});

$("midday-form").addEventListener("submit", (event) => {
  event.preventDefault();
  const exercises = Array.from(document.querySelectorAll(".exercise-row")).map((row) => ({ name: row.querySelector(".exercise-name").value.trim(), amount: row.querySelector(".exercise-amount").value, unit: row.querySelector(".exercise-unit").value })).filter((exercise) => exercise.name || exercise.amount);
  const totalDuration = exercises.filter((exercise) => exercise.unit === "minutes").reduce((sum, exercise) => sum + (Number(exercise.amount) || 0), 0);
  runPhase({ phase: "midday", button: $("midday-submit"), checkIn: { date: $("log-date").value, exercises, totalDuration, planAdherence: $("plan-adherence").value, effort: $("workout-effort").value, notes: $("workout-notes").value.trim() } });
});

$("evening-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  try {
    const imageData = await Promise.all(photos.map(fileToDataUrl));
    runPhase({ phase: "evening", button: $("evening-submit"), images: imageData, checkIn: { date: $("log-date").value, food: $("food").value.trim(), bowelFrequency: $("bowel-frequency").value, bowelForm: $("bowel-form").value, bowelSymptoms: $("bowel-symptoms").value, notes: $("evening-notes").value.trim() } });
  } catch (error) { setStatus(error.message, "error"); }
});

$("log-date").addEventListener("change", populateForms);
$("clear-plan").addEventListener("click", showEmptyCoach);
switchPhase(activePhase, false);
applyLanguage();

fetch("/api/me", { credentials: "same-origin" }).then((response) => response.json()).then(async ({ user }) => {
  if (user) { showApp(user); await loadRecords(); }
}).catch(() => setStatus("记录服务未连接", "error"));
