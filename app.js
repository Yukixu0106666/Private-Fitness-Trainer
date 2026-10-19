const $ = (id) => document.getElementById(id);
const today = new Date();
const isoDate = (date) => {
  const local = new Date(date.getTime() - date.getTimezoneOffset() * 60000);
  return local.toISOString().slice(0, 10);
};

let photos = [];
let photoPreviewUrls = [];
let records = [];
let profile = {};
let exerciseProgress = [];
let registerMode = false;
let progressDays = 14;
let activePhase = today.getHours() < 11 ? "morning" : today.getHours() < 18 ? "midday" : "evening";
let language = localStorage.getItem("fitness-coach-language") || "zh";

const enText = {
  "我的健身教练": "My Fitness Coach", "记录今天，获得更适合明天的训练建议。": "Log today and get guidance for a better tomorrow.",
  "退出登录": "Log out", "登录": "Log in", "注册": "Sign up", "邮箱": "Email", "密码（至少 8 位）": "Password (at least 8 characters)",
  "还没有账号？注册": "No account yet? Sign up", "已有账号？登录": "Already have an account? Log in", "注册并登录": "Sign up and log in",
  "今天的教练": "Today's coach", "早": "AM", "中": "MID", "晚": "PM", "早上计划": "Morning plan", "状态与今日安排": "Status and daily plan",
  "训练完成": "Workout done", "运动与拉伸": "Exercise and stretching", "晚上复盘": "Evening review", "饮食与排便": "Food and digestion",
  "早上好，先看看今天的身体状态": "Good morning — let's check how your body feels", "你的目标": "Your goal", "减脂塑形": "Fat loss & shaping",
  "增肌增力": "Build muscle & strength", "提升体能": "Improve fitness", "保持健康": "Stay healthy", "身高（cm）": "Height (cm)", "晨起体重（kg）": "Morning weight (kg)",
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
  "长期记忆设置": "Long-term memory", "由你确认后保存": "saved only after your confirmation", "可用器械": "Available equipment", "饮食偏好或限制": "Dietary preferences or restrictions", "长期身体限制": "Long-term physical constraints", "只填写希望教练长期记住的信息": "Only enter information you want the coach to remember",
  "数据与账号管理": "Data and account management", "你可以导出所有打卡、长期画像和 AI 建议。": "Export all check-ins, your long-term profile, and AI guidance.",
  "导出个人数据": "Export personal data", "清空长期记忆": "Clear long-term memory", "永久删除账号": "Permanently delete account",
  "这会删除所有打卡、AI 建议、请求追踪和向量记忆，且无法恢复。": "This deletes every check-in, AI response, request trace, and vector memory and cannot be undone.",
  "输入密码确认": "Enter your password to confirm", "可以从早上的计划一键带入，再勾选和修改实际完成量。": "Import the morning plan, then check off and adjust what you completed.",
  "进度趋势": "Progress trends", "体重趋势": "Weight trend", "圆点为记录值，线条为移动平均": "Dots are entries; the line is a moving average",
  "恢复状态": "Recovery", "睡眠与精力变化": "Sleep and energy trends", "完成打卡后，这里会显示你的趋势": "Your trends will appear after you check in",
  "连续记录几天，就能看见体重、恢复和训练变化。": "Log a few days to see changes in weight, recovery, and training."
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
      "例如：168": "e.g. 168", "例如：55.05": "e.g. 55.05", "运动名称，如快走": "Exercise, e.g. brisk walking", "例如：右膝不舒服，今天只能在家练": "e.g. My right knee hurts; I can only train at home",
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

function unitLabel(unit, amount) {
  if (language === "en") return unit === "reps" ? "reps" : unit === "seconds" ? "sec" : "min";
  return unit === "reps" ? "次" : unit === "seconds" ? "秒" : "分钟";
}

function normalizePlanItem(item, index = 0) {
  if (typeof item === "string") return { name: item, sets: "", amount: "", unit: "minutes", intensity: "", restSeconds: "", planIndex: index };
  return {
    name: item?.name || "", sets: item?.sets ?? "", amount: item?.amount ?? "",
    unit: item?.unit || "reps", intensity: item?.intensity || "",
    restSeconds: item?.restSeconds ?? "", planIndex: index,
  };
}

function exerciseKey(value) {
  return String(value || "").normalize("NFKC").trim().toLocaleLowerCase().replace(/[\s\-_]+/g, "");
}

function formatPerformance(entry) {
  if (!entry) return language === "en" ? "no completed session" : "暂无完成记录";
  const amount = entry.amount ?? "—";
  const sets = entry.sets ?? 1;
  const load = Number(entry.loadKg) > 0 ? ` @ ${entry.loadKg} kg` : "";
  return `${sets} × ${amount} ${unitLabel(entry.unit, amount)}${load}`;
}

function suggestionText(suggestion) {
  if (!suggestion || suggestion.action === "baseline") {
    return language === "en" ? "Complete one session to establish a baseline." : "先完成一次，建立这个动作的基线。";
  }
  const target = formatPerformance(suggestion.target);
  if (suggestion.action === "increase") {
    return language === "en" ? `Two comfortable completions: try ${target} next time.` : `连续两次适中强度完成，下次可尝试 ${target}。`;
  }
  if (suggestion.action === "reduce") {
    return language === "en" ? `Missed twice in a row: step back to ${target}.` : `连续两次未完成，建议回退到 ${target}。`;
  }
  const reason = suggestion.reason === "recent_effort_high"
    ? (language === "en" ? "The last effort was high" : "上次强度较高")
    : suggestion.reason === "recent_incomplete"
      ? (language === "en" ? "The last session was incomplete" : "上次未完成")
      : (language === "en" ? "Build consistency first" : "先稳定完成")
  return language === "en" ? `${reason}: maintain ${target}.` : `${reason}，下次维持 ${target}。`;
}

function updateExerciseHistory(row) {
  const element = row.querySelector(".exercise-history");
  const key = exerciseKey(row.querySelector(".exercise-name").value);
  const summary = exerciseProgress.find((item) => item.key === key);
  if (!key || !summary) {
    element.classList.add("hidden");
    element.innerHTML = "";
    return;
  }
  const recent = summary.recent28Days || {};
  const rate = recent.sessions ? `${recent.completed}/${recent.sessions}` : "0/0";
  const best = summary.best ? formatPerformance(summary.best) : "—";
  element.innerHTML = `<span>${language === "en" ? "Last" : "上次"} <strong>${escapeHtml(summary.lastCompleted?.date || "—")}</strong> · ${escapeHtml(formatPerformance(summary.lastCompleted))}</span>
    <span>${language === "en" ? "Last 4 weeks" : "近 4 周"} <strong>${escapeHtml(rate)}</strong> ${language === "en" ? "completed" : "次完成"} · ${language === "en" ? "best" : "最佳"} ${escapeHtml(best)}</span>
    <span class="exercise-next ${escapeHtml(summary.suggestion?.action || "baseline")}">${escapeHtml(suggestionText(summary.suggestion))}</span>`;
  element.classList.remove("hidden");
}

function refreshExerciseHistory() {
  document.querySelectorAll(".exercise-row").forEach(updateExerciseHistory);
}

function addExerciseRow(exercise = {}) {
  const name = exercise.name || "";
  const amount = exercise.amount ?? exercise.duration ?? "";
  const unit = exercise.unit || "minutes";
  const completed = exercise.completed !== false;
  const row = document.createElement("div");
  row.className = "exercise-row";
  if (exercise.planIndex !== undefined && exercise.planIndex !== null) row.dataset.planIndex = exercise.planIndex;
  row.innerHTML = `<div class="exercise-row-main"><label class="exercise-check"><input class="exercise-completed" type="checkbox"${completed ? " checked" : ""} /><span>${language === "en" ? "Done" : "完成"}</span></label><input class="exercise-name" type="text" placeholder="${language === "en" ? "Exercise, e.g. brisk walking" : "运动名称，如快走"}" value="${escapeHtml(name)}" /><button class="remove-exercise" type="button" aria-label="${language === "en" ? "Remove exercise" : "删除这项运动"}">×</button></div>
    <div class="exercise-details">
      <label><span>${language === "en" ? "Sets" : "组数"}</span><input class="exercise-sets" type="number" min="1" max="100" step="1" placeholder="1" value="${escapeHtml(exercise.sets ?? "")}" /></label>
      <label><span>${language === "en" ? "Amount / set" : "每组数量"}</span><input class="exercise-amount" type="number" min="0" max="10000" step="0.5" placeholder="10" value="${escapeHtml(amount)}" /></label>
      <label><span>${language === "en" ? "Unit" : "单位"}</span><select class="exercise-unit" aria-label="${language === "en" ? "Unit" : "单位"}"><option value="reps"${unit === "reps" ? " selected" : ""}>${language === "en" ? "reps" : "次"}</option><option value="minutes"${unit === "minutes" ? " selected" : ""}>${language === "en" ? "min" : "分钟"}</option><option value="seconds"${unit === "seconds" ? " selected" : ""}>${language === "en" ? "sec" : "秒"}</option></select></label>
      <label><span>${language === "en" ? "Load (kg)" : "负重（kg）"}</span><input class="exercise-load" type="number" min="0" max="1000" step="0.5" placeholder="—" value="${escapeHtml(exercise.loadKg ?? "")}" /></label>
    </div>
    ${exercise.intensity || exercise.restSeconds !== "" ? `<p class="exercise-target">${language === "en" ? "Target" : "计划"}：${escapeHtml(exercise.intensity)}${exercise.restSeconds !== "" ? ` · ${language === "en" ? "rest" : "休息"} ${escapeHtml(exercise.restSeconds)} ${language === "en" ? "sec" : "秒"}` : ""}</p>` : ""}
    <div class="exercise-history hidden" aria-live="polite"></div>`;
  row.querySelector(".remove-exercise").addEventListener("click", () => {
    row.remove();
    if (!$("exercise-list").children.length) {
      addExerciseRow();
      applyLanguage();
    }
    syncPlanAdherenceFromExercises();
  });
  row.querySelector(".exercise-completed").addEventListener("change", syncPlanAdherenceFromExercises);
  row.querySelector(".exercise-name").addEventListener("input", () => updateExerciseHistory(row));
  $("exercise-list").appendChild(row);
  updateExerciseHistory(row);
}

function syncPlanAdherenceFromExercises() {
  const plannedRows = Array.from(document.querySelectorAll(".exercise-row[data-plan-index]"));
  if (!plannedRows.length) return;
  const completed = plannedRows.filter((row) => row.querySelector(".exercise-completed").checked).length;
  setValue("plan-adherence", completed === plannedRows.length ? "all" : completed === 0 ? "none" : "partial");
}

$("add-exercise").addEventListener("click", () => {
  addExerciseRow();
  applyLanguage();
});

function showApp(user) {
  $("auth-card").classList.toggle("hidden", !!user);
  $("app-content").classList.toggle("hidden", !user);
  $("history-content").classList.toggle("hidden", !user);
  $("progress-content").classList.toggle("hidden", !user);
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
  exerciseProgress = [];
  renderHistory();
  renderProgress();
  showApp(null);
});

function setDataActionStatus(message, error = false) {
  $("data-action-status").textContent = message;
  $("data-action-status").classList.toggle("error", error);
}

$("export-data").addEventListener("click", async () => {
  setDataActionStatus(language === "en" ? "Preparing export…" : "正在准备导出…");
  try {
    const response = await fetch("/api/export", { credentials: "same-origin" });
    if (!response.ok) {
      const result = await response.json().catch(() => ({}));
      throw new Error(result.error || (language === "en" ? "Could not export data" : "无法导出数据"));
    }
    const blob = await response.blob();
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `fitness-coach-export-${isoDate(new Date())}.json`;
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(url);
    setDataActionStatus(language === "en" ? "Export downloaded." : "个人数据已下载。");
  } catch (error) { setDataActionStatus(error.message, true); }
});

$("clear-profile").addEventListener("click", async () => {
  const confirmed = window.confirm(language === "en" ? "Clear your confirmed long-term profile? Daily records will be kept." : "确定清空已确认的长期记忆吗？每日打卡会保留。");
  if (!confirmed) return;
  try {
    const result = await authRequest("/api/profile/clear", {});
    profile = result.profile?.confirmed || {};
    populateForms();
    setDataActionStatus(language === "en" ? "Long-term memory cleared." : "长期记忆已清空。");
  } catch (error) { setDataActionStatus(error.message, true); }
});

$("delete-account").addEventListener("click", async () => {
  const password = $("delete-account-password").value;
  if (!password) {
    setDataActionStatus(language === "en" ? "Enter your password first." : "请先输入密码。", true);
    return;
  }
  const confirmed = window.confirm(language === "en" ? "Permanently delete this account and all its data? This cannot be undone." : "确定永久删除账号及全部数据吗？此操作无法恢复。");
  if (!confirmed) return;
  try {
    await authRequest("/api/account/delete", { password });
    records = [];
    profile = {};
    $("delete-account-password").value = "";
    renderHistory();
    showApp(null);
    setStatus(language === "en" ? "Account deleted" : "账号已删除");
  } catch (error) { setDataActionStatus(error.message, true); }
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
  if (photos.length) renderPhotoPreviews();
  renderHistory();
  renderProgress();
  renderSavedResponse();
  refreshExerciseHistory();
});

function renderPhotoPreviews(message = "") {
  photoPreviewUrls.forEach((url) => URL.revokeObjectURL(url));
  photoPreviewUrls = [];
  const preview = $("photo-preview");
  preview.innerHTML = "";
  if (message || !photos.length) {
    const hint = document.createElement("div");
    hint.className = "upload-hint";
    hint.textContent = message || tr("可上传餐食照片帮助 AI 判断搭配");
    preview.appendChild(hint);
    return;
  }
  photos.forEach((photo, index) => {
    const item = document.createElement("div");
    item.className = "photo-item";
    const image = document.createElement("img");
    const url = URL.createObjectURL(photo);
    photoPreviewUrls.push(url);
    image.src = url;
    image.alt = language === "en" ? `Food photo ${index + 1}` : `饮食照片 ${index + 1}`;
    const remove = document.createElement("button");
    remove.className = "remove-photo";
    remove.type = "button";
    remove.textContent = "×";
    remove.setAttribute("aria-label", language === "en" ? `Remove food photo ${index + 1}` : `删除饮食照片 ${index + 1}`);
    remove.addEventListener("click", () => {
      photos.splice(index, 1);
      if (!photos.length) $("food-photos").value = "";
      renderPhotoPreviews();
    });
    item.append(image, remove);
    preview.appendChild(item);
  });
}

$("food-photos").addEventListener("change", (event) => {
  const selected = Array.from(event.target.files || []);
  const supported = new Set(["image/jpeg", "image/png", "image/webp"]);
  if (selected.length > 4 || selected.some((photo) => !supported.has(photo.type) || photo.size > 4 * 1024 * 1024)) {
    photos = [];
    event.target.value = "";
    renderPhotoPreviews(language === "en" ? "Choose up to 4 JPEG, PNG, or WebP images, no more than 4 MB each." : "最多选择 4 张 JPEG、PNG 或 WebP 图片，每张不超过 4 MB。");
    return;
  }
  photos = selected;
  renderPhotoPreviews();
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

function trainingItems(items) {
  if (!Array.isArray(items) || !items.length) return "";
  return `<div class="training-plan-list">${items.map((item) => {
    const normalized = normalizePlanItem(item);
    const structured = item && typeof item === "object";
    const prescription = `${normalized.sets} × ${normalized.amount} ${unitLabel(normalized.unit, normalized.amount)}`;
    const rest = normalized.restSeconds ? ` · ${language === "en" ? "rest" : "休息"} ${normalized.restSeconds}${language === "en" ? " sec" : " 秒"}` : "";
    return `<div class="training-plan-item"><strong>${escapeHtml(normalized.name)}</strong>${structured ? `<span>${escapeHtml(prescription)}</span><small>${escapeHtml(normalized.intensity)}${escapeHtml(rest)}</small>` : ""}</div>`;
  }).join("")}</div><button id="use-training-plan" class="secondary-button use-training-plan" type="button">${language === "en" ? "Use this as workout log" : "一键带入训练记录"} <span>→</span></button>`;
}

function bindTrainingPlan(items) {
  const button = $("use-training-plan");
  if (!button || !Array.isArray(items)) return;
  button.addEventListener("click", () => {
    $("exercise-list").innerHTML = "";
    items.forEach((item, index) => addExerciseRow({ ...normalizePlanItem(item, index), completed: false }));
    syncPlanAdherenceFromExercises();
    switchPhase("midday", false);
    $("midday-form").scrollIntoView({ behavior: "smooth", block: "start" });
  });
}

function isValidScore(value) {
  if (value === null || value === undefined || value === "") return false;
  const score = Number(value);
  return Number.isFinite(score) && score >= 0 && score <= 100;
}

function renderCoachResponse(response, phase) {
  if (!response) return showEmptyCoach();
  $("empty-plan").classList.add("hidden");
  $("plan-content").classList.remove("hidden");
  $("plan-title").textContent = response.title || (phase === "morning" ? "今日计划" : phase === "midday" ? "拉伸建议" : "今日复盘");
  if (response.safetyAlert) {
    const urgent = response.safetyAlert.level === "emergency";
    const heading = language === "en" ? (urgent ? "Urgent medical attention" : "Medical assessment recommended") : (urgent ? "请立即寻求医疗帮助" : "建议尽快进行医疗评估");
    $("plan-content").innerHTML = `<div class="safety-alert ${urgent ? "emergency" : "medical-attention"}"><span class="safety-label">${escapeHtml(heading)}</span><strong>${escapeHtml(response.title)}</strong><p>${escapeHtml(response.summary)}</p>${list(response.safetyAlert.actions)}</div>`;
  } else if (phase === "morning") {
    const evaluation = response.previousDayEvaluation;
    const hasScore = evaluation && isValidScore(evaluation.score);
    const score = hasScore ? `<div class="score-card"><div class="score-number">${escapeHtml(evaluation.score)}<small>/100</small></div><div><strong>昨天表现</strong><p>${escapeHtml(evaluation.summary)}</p></div></div>` : "";
    const meals = response.meals || {};
    $("plan-content").innerHTML = `${score}<div class="plan-intro"><strong>${escapeHtml(response.title)}</strong><br />${escapeHtml(response.summary)}</div>
      <div class="plan-section"><span class="tag">${escapeHtml(response.training?.loadLabel || "今日训练")}</span><h3>今天的运动</h3>${trainingItems(response.training?.items)}</div>
      <div class="plan-section"><h3>今天怎么吃</h3><div class="meal-grid"><p><strong>早餐</strong>${escapeHtml(meals.breakfast || "均衡早餐")}</p><p><strong>午餐</strong>${escapeHtml(meals.lunch || "均衡午餐")}</p><p><strong>晚餐</strong>${escapeHtml(meals.dinner || "均衡晚餐")}</p></div>${meals.principles ? `<p>${escapeHtml(meals.principles)}</p>` : ""}</div>
      <div class="plan-section"><h3>恢复提醒</h3><p>${escapeHtml(response.recovery || "根据身体感受调整强度。")}</p></div>`;
  } else if (phase === "midday") {
    $("plan-content").innerHTML = `<div class="plan-intro"><strong>${escapeHtml(response.title)}</strong><br />${escapeHtml(response.summary)}</div><div class="plan-section"><span class="tag">${escapeHtml(response.stretch?.duration || "8–12 分钟")}</span><h3>现在这样拉伸</h3>${list(response.stretch?.items)}</div><div class="plan-section"><h3>安全提醒</h3><p>${escapeHtml(response.stretch?.safety || "拉伸保持轻柔，不要追求疼痛感。")}</p></div>`;
  } else {
    $("plan-content").innerHTML = `<div class="plan-intro"><strong>${escapeHtml(response.title)}</strong><br />${escapeHtml(response.summary)}</div><div class="plan-section"><h3>今天做得好的地方</h3>${list(response.wins)}</div><div class="plan-section"><h3>明早评分会关注</h3>${list(response.tomorrowScoreFactors)}</div><div class="plan-section"><h3>今晚提醒</h3><p>${escapeHtml(response.tonightTip || "早点休息并适量补水。")}</p></div>`;
  }
  if (phase === "morning") bindTrainingPlan(response.training?.items);
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
    if (source.type === "server_derived_exercise_progress") return language === "en" ? "exercise progression history" : "动作渐进历史";
    if (source.type === "tool_daily_record") return `${language === "en" ? "extra record" : "补充记录"} ${source.date}`;
    if (source.type === "tool_recent_records") return language === "en" ? "extra recent records" : "补充近期记录";
    if (source.type === "tool_derived_weight_trend") return language === "en" ? "extra weight trend" : "补充体重趋势";
    if (source.type === "hybrid_pgvector_reranked") return language === "en" ? "reranked semantic history" : "向量召回与重排历史";
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
  setValue("profile-height", profile.height ?? record.height);
  setValue("profile-equipment", profile.equipment); setValue("profile-diet", profile.dietaryPreferences); setValue("profile-constraints", profile.constraints);
  setValue("energy", morning.energy, "3"); setValue("soreness", morning.soreness, "2"); setValue("available-time", morning.availableTime, "45"); setValue("morning-notes", morning.notes);
  $("exercise-list").innerHTML = "";
  const exercises = Array.isArray(midday.exercises) && midday.exercises.length ? midday.exercises : midday.workout ? [{ name: midday.workout, duration: midday.duration || "" }] : [{ name: "", duration: "" }];
  exercises.forEach((exercise) => addExerciseRow(exercise));
  setValue("plan-adherence", midday.planAdherence, "partial"); setValue("workout-effort", midday.effort, "3"); setValue("workout-notes", midday.notes);
  setValue("food", evening.food); setValue("bowel-frequency", evening.bowelFrequency, "1"); setValue("bowel-form", evening.bowelForm, "normal"); setValue("bowel-symptoms", evening.bowelSymptoms, "none"); setValue("evening-notes", evening.notes);
  $("morning-saved").textContent = record.morning || record.weight ? "✓ 已保存" : "";
  $("midday-saved").textContent = record.midday ? "✓ 已保存" : "";
  $("evening-saved").textContent = record.evening ? "✓ 已保存" : "";
  renderSavedResponse();
  applyLanguage();
}

function renderHistory() {
  $("record-count").textContent = language === "en" ? `${records.length} days` : `${records.length} 天记录`;
  $("history-list").innerHTML = records.length ? records.slice(0, 14).map((record) => {
    const nextRecord = records.find((item) => priorDate(item.date) === record.date);
    const score = nextRecord?.plan?.previousDayEvaluation?.score;
    const scoreSummary = isValidScore(score)
      ? ` · ${language === "en" ? "Next-day score" : "次日评分"} ${escapeHtml(score)}/100`
      : ` · ${language === "en" ? "Waiting for next-day score" : "等待次日评分"}`;
    const morning = record.morning || record;
    const phases = [record.morning || record.weight, record.midday, record.evening].filter(Boolean).length;
    const phaseSummary = language === "en" ? `${phases}/3 phases logged` : `${phases}/3 阶段已记录`;
    const deleteLabel = language === "en" ? `Delete record for ${record.date}` : `删除 ${record.date} 记录`;
    return `<div class="history-item"><div class="history-date">${escapeHtml(record.date)}</div><div class="history-summary">${morning.weight ? `${escapeHtml(morning.weight)} kg · ` : ""}${phaseSummary}${scoreSummary}</div><button class="delete-record" type="button" data-date="${escapeHtml(record.date)}" aria-label="${escapeHtml(deleteLabel)}">${language === "en" ? "Delete" : "删除"}</button></div>`;
  }).join("") : `<p class="muted">${language === "en" ? "Your records will appear here after your first morning check-in." : "完成第一次早间打卡后，这里会显示你的记录。"}</p>`;
  applyLanguage();
}

function dateNumber(date) {
  const value = new Date(`${date}T12:00:00`).getTime();
  return Number.isFinite(value) ? value : null;
}

function numericValue(value) {
  if (value === null || value === undefined || value === "") return null;
  const number = Number(value);
  return Number.isFinite(number) ? number : null;
}

function average(values) {
  const valid = values.map(numericValue).filter((value) => value !== null);
  return valid.length ? valid.reduce((sum, value) => sum + value, 0) / valid.length : null;
}

function phaseCount(record) {
  return [record.morning || record.weight, record.midday, record.evening].filter(Boolean).length;
}

function progressRecords(days) {
  const end = new Date();
  end.setHours(23, 59, 59, 999);
  const start = new Date(end);
  start.setDate(start.getDate() - days + 1);
  start.setHours(0, 0, 0, 0);
  return records.filter((record) => {
    const value = dateNumber(record.date);
    return value !== null && value >= start.getTime() && value <= end.getTime();
  }).sort((a, b) => a.date.localeCompare(b.date));
}

function currentStreak() {
  const dates = new Set(records.map((record) => record.date));
  const cursor = new Date();
  if (!dates.has(isoDate(cursor))) cursor.setDate(cursor.getDate() - 1);
  let count = 0;
  while (dates.has(isoDate(cursor))) {
    count += 1;
    cursor.setDate(cursor.getDate() - 1);
  }
  return count;
}

function workoutStats(items) {
  let days = 0;
  let minutes = 0;
  items.forEach((record) => {
    const midday = record.midday || {};
    const exercises = Array.isArray(midday.exercises) ? midday.exercises : [];
    const completed = exercises.filter((exercise) => exercise.completed !== false);
    const recordedMinutes = numericValue(midday.totalDuration);
    if (completed.length || (recordedMinutes !== null && recordedMinutes > 0)) days += 1;
    if (recordedMinutes !== null && recordedMinutes > 0) minutes += recordedMinutes;
  });
  return { days, minutes: Math.round(minutes) };
}

function movingAverage(samples, windowSize = 7) {
  return samples.map((sample, index) => ({
    ...sample,
    average: average(samples.slice(Math.max(0, index - windowSize + 1), index + 1).map((item) => item.value)),
  }));
}

function lineChart(samples, options = {}) {
  if (!samples.length) return `<div class="chart-empty">${language === "en" ? "Not enough data yet" : "数据还不够，继续记录几天吧"}</div>`;
  const width = 520, height = 178, left = 38, right = 14, top = 12, bottom = 28;
  const plotWidth = width - left - right, plotHeight = height - top - bottom;
  const chartKeys = options.dotsKey ? [...options.valueKeys, options.dotsKey] : options.valueKeys;
  const values = samples.flatMap((sample) => chartKeys.map((key) => numericValue(sample[key]))).filter((value) => value !== null);
  let min = options.min ?? Math.min(...values), max = options.max ?? Math.max(...values);
  if (min === max) { min -= 1; max += 1; }
  const padding = options.fixedRange ? 0 : Math.max((max - min) * 0.12, options.minimumPadding || 0.2);
  min -= padding; max += padding;
  const firstDate = Math.min(...samples.map((sample) => sample.time));
  const lastDate = Math.max(...samples.map((sample) => sample.time));
  const x = (sample, index) => lastDate === firstDate ? left + plotWidth / 2 : left + ((sample.time - firstDate) / (lastDate - firstDate)) * plotWidth;
  const y = (value) => top + ((max - value) / (max - min)) * plotHeight;
  const grids = [0, .5, 1].map((ratio) => {
    const gridY = top + ratio * plotHeight;
    const label = (max - ratio * (max - min)).toFixed(options.decimals ?? 1);
    return `<line class="chart-grid" x1="${left}" y1="${gridY}" x2="${width - right}" y2="${gridY}"/><text class="chart-axis-label" x="${left - 5}" y="${gridY + 3}" text-anchor="end">${label}</text>`;
  }).join("");
  const paths = options.valueKeys.map((key, keyIndex) => {
    const points = samples.map((sample, index) => numericValue(sample[key]) !== null ? `${x(sample, index)},${y(numericValue(sample[key]))}` : null).filter(Boolean);
    return points.length ? `<polyline class="chart-line${keyIndex ? " secondary" : ""}" points="${points.join(" ")}"/>` : "";
  }).join("");
  const dots = options.dotsKey ? samples.map((sample, index) => numericValue(sample[options.dotsKey]) !== null ? `<circle class="chart-dot" cx="${x(sample, index)}" cy="${y(numericValue(sample[options.dotsKey]))}" r="3.5"/>` : "").join("") : "";
  const dateLabel = (date) => date.slice(5).replace("-", "/");
  return `<svg viewBox="0 0 ${width} ${height}" role="img" aria-label="${escapeHtml(options.label || "Trend chart")}">${grids}${paths}${dots}<text class="chart-axis-label" x="${left}" y="${height - 7}">${escapeHtml(dateLabel(samples[0].date))}</text><text class="chart-axis-label" x="${width - right}" y="${height - 7}" text-anchor="end">${escapeHtml(dateLabel(samples[samples.length - 1].date))}</text></svg>${options.legend || ""}`;
}

function periodStats(items) {
  const mornings = items.map((record) => record.morning || record);
  const weights = mornings.map((morning) => numericValue(morning.weight)).filter((value) => value !== null);
  const sleep = mornings.map((morning) => numericValue(morning.sleep)).filter((value) => value !== null);
  const energy = mornings.map((morning) => numericValue(morning.energy)).filter((value) => value !== null);
  const phases = items.reduce((sum, record) => sum + phaseCount(record), 0);
  return {
    weightChange: weights.length > 1 ? weights[weights.length - 1] - weights[0] : null,
    averageSleep: average(sleep), averageEnergy: average(energy),
    phaseRate: items.length ? phases / (items.length * 3) : 0,
    ...workoutStats(items),
  };
}

function renderProgressInsights(items, stats) {
  const midpoint = Math.floor(items.length / 2);
  const earlier = periodStats(items.slice(0, midpoint));
  const recent = periodStats(items.slice(midpoint));
  let win;
  if (items.length >= 4 && recent.phaseRate > earlier.phaseRate + .1) win = language === "en" ? "Your check-in completion improved in the latter half of this period." : "后半段的打卡完整度比前半段更高。";
  else if (items.length >= 4 && recent.averageSleep && earlier.averageSleep && recent.averageSleep > earlier.averageSleep + .25) win = language === "en" ? "Your average sleep improved in the latter half of this period." : "后半段的平均睡眠比前半段有所提升。";
  else if (stats.days >= 2) win = language === "en" ? `You completed workouts on ${stats.days} days and logged ${stats.minutes} minutes.` : `这段时间完成了 ${stats.days} 天训练，共记录 ${stats.minutes} 分钟。`;
  else win = language === "en" ? `You recorded ${items.length} days. Consistency will make the trends more useful.` : `已记录 ${items.length} 天；继续保持，趋势会越来越有参考价值。`;

  let focus;
  if (stats.averageSleep !== null && stats.averageSleep < 7) focus = language === "en" ? "Average sleep is below 7 hours. Prioritize a steadier bedtime next." : "平均睡眠不足 7 小时，下一阶段优先稳定入睡时间。";
  else if (stats.phaseRate < .75) focus = language === "en" ? "Some daily stages are missing. Try completing one more stage on recorded days." : "部分日期缺少阶段记录，下一步先争取每天多完成一个阶段。";
  else if (stats.days === 0) focus = language === "en" ? "No completed workout was recorded in this period. Start with one manageable session." : "这段时间还没有完成训练记录，可以先安排一次容易完成的短训练。";
  else if (stats.averageEnergy !== null && stats.averageEnergy < 3) focus = language === "en" ? "Energy has been relatively low. Keep training load conservative and watch recovery." : "近期精力偏低，训练量先保持保守，并继续观察恢复。";
  else focus = language === "en" ? "Keep the current rhythm and focus on accurate workout completion logs." : "保持当前节奏，下一阶段重点记录真实完成量。";
  $("progress-insights").innerHTML = `<div class="insight-card positive"><span>${language === "en" ? "A recent win" : "最近的一个进步"}</span><strong>${escapeHtml(win)}</strong></div><div class="insight-card focus"><span>${language === "en" ? "Next focus" : "下一阶段重点"}</span><strong>${escapeHtml(focus)}</strong></div>`;
}

function renderProgress() {
  document.querySelector(".range-toggle").setAttribute("aria-label", language === "en" ? "Progress date range" : "进度统计范围");
  document.querySelectorAll(".range-toggle button").forEach((button) => {
    button.classList.toggle("active", Number(button.dataset.days) === progressDays);
    button.textContent = `${button.dataset.days} ${language === "en" ? "days" : "天"}`;
  });
  const items = progressRecords(progressDays);
  $("progress-empty").classList.toggle("hidden", !!items.length);
  $("progress-dashboard").classList.toggle("hidden", !items.length);
  if (!items.length) return;
  const stats = periodStats(items);
  const weightText = stats.weightChange === null ? "—" : `${stats.weightChange > 0 ? "+" : ""}${stats.weightChange.toFixed(1)} kg`;
  $("progress-metrics").innerHTML = [
    [language === "en" ? "Weight change" : "体重变化", weightText, language === "en" ? `${items.length} recorded days` : `${items.length} 天有记录`],
    [language === "en" ? "Training" : "训练完成", `${stats.days} ${language === "en" ? "days" : "天"}`, `${stats.minutes} ${language === "en" ? "minutes" : "分钟"}`],
    [language === "en" ? "Average sleep" : "平均睡眠", stats.averageSleep === null ? "—" : `${stats.averageSleep.toFixed(1)} h`, stats.averageEnergy === null ? "—" : `${language === "en" ? "Energy" : "精力"} ${stats.averageEnergy.toFixed(1)}/5`],
    [language === "en" ? "Stage completion" : "阶段完成率", `${Math.round(stats.phaseRate * 100)}%`, `${language === "en" ? "Current streak" : "连续记录"} ${currentStreak()} ${language === "en" ? "days" : "天"}`],
  ].map(([label, value, detail]) => `<div class="progress-metric"><span>${escapeHtml(label)}</span><strong>${escapeHtml(value)}</strong><small>${escapeHtml(detail)}</small></div>`).join("");

  const weightSamples = items.map((record) => ({ date: record.date, time: dateNumber(record.date), value: numericValue((record.morning || record).weight) })).filter((sample) => sample.value !== null);
  const weightTrend = movingAverage(weightSamples).map((sample) => ({ ...sample, moving: sample.average }));
  $("weight-chart").innerHTML = lineChart(weightTrend, { valueKeys: ["moving"], dotsKey: "value", label: language === "en" ? "Weight trend" : "体重趋势", decimals: 1, minimumPadding: .2 });
  $("weight-trend-label").textContent = weightText;

  const recoverySamples = items.map((record) => {
    const morning = record.morning || record;
    const energy = numericValue(morning.energy);
    return { date: record.date, time: dateNumber(record.date), sleep: numericValue(morning.sleep), energyScaled: energy === null ? null : energy * 2 };
  }).filter((sample) => sample.sleep !== null || sample.energyScaled !== null);
  const legend = `<div class="chart-legend"><span class="legend-item">${language === "en" ? "Sleep (h)" : "睡眠（小时）"}</span><span class="legend-item energy">${language === "en" ? "Energy (×2)" : "精力（×2）"}</span></div>`;
  $("recovery-chart").innerHTML = lineChart(recoverySamples, { valueKeys: ["sleep", "energyScaled"], label: language === "en" ? "Sleep and energy trend" : "睡眠与精力趋势", min: 0, max: 10, fixedRange: true, decimals: 0, legend });
  $("recovery-trend-label").textContent = stats.averageSleep === null ? "—" : `${language === "en" ? "Avg" : "平均"} ${stats.averageSleep.toFixed(1)}h`;
  renderProgressInsights(items, stats);
}

document.querySelectorAll(".range-toggle button").forEach((button) => button.addEventListener("click", () => {
  progressDays = Number(button.dataset.days);
  renderProgress();
}));

$("history-list").addEventListener("click", async (event) => {
  const button = event.target.closest(".delete-record");
  if (!button) return;
  const date = button.dataset.date;
  const confirmed = window.confirm(language === "en" ? `Delete all records and AI guidance for ${date}?` : `确定删除 ${date} 的全部打卡和 AI 建议吗？`);
  if (!confirmed) return;
  button.disabled = true;
  try {
    await authRequest("/api/records/delete", { date });
    records = records.filter((record) => record.date !== date);
    renderHistory();
    renderProgress();
    populateForms();
    setDataActionStatus(language === "en" ? `Record for ${date} deleted.` : `${date} 的记录已删除。`);
  } catch (error) {
    button.disabled = false;
    setDataActionStatus(error.message, true);
  }
});

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
  renderHistory(); renderProgress(); populateForms();
}

async function loadRecords() {
  const response = await fetch("/api/records", { credentials: "same-origin" });
  const result = await response.json().catch(() => ({}));
  if (response.status === 401) return;
  if (!response.ok) throw new Error(result.error || (language === "en" ? "Could not load records" : "无法读取历史记录"));
  records = Array.isArray(result.records) ? result.records : [];
  profile = result.profile?.confirmed || {};
  renderHistory(); renderProgress(); populateForms();
  await loadExerciseProgress().catch((error) => setStatus(error.message, "error"));
}

async function loadExerciseProgress() {
  const requestedDate = $("log-date").value;
  const response = await fetch(`/api/exercise-progress?before=${encodeURIComponent(requestedDate)}`, { credentials: "same-origin" });
  const result = await response.json().catch(() => ({}));
  if (response.status === 401) return;
  if (!response.ok) throw new Error(result.error || (language === "en" ? "Could not load exercise history" : "无法读取动作历史"));
  if ($("log-date").value !== requestedDate) return;
  exerciseProgress = Array.isArray(result.exercises) ? result.exercises : [];
  refreshExerciseHistory();
}

async function runPhase({ phase, button, checkIn, images = [] }) {
  const original = button.innerHTML;
  const factualCheckIn = { ...checkIn };
  const profileUpdate = factualCheckIn.profileUpdate;
  delete factualCheckIn.profileUpdate;
  const height = Number($("profile-height").value);
  const existing = currentRecord() || { date: $("log-date").value };
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
    const safetyInterception = result.agent?.safetyInterception;
    const observed = result.observability;
    const telemetry = observed ? ` · ${(Number(observed.durationMs) / 1000).toFixed(1)}s${observed.estimatedCostUsd === null ? "" : ` · $${Number(observed.estimatedCostUsd).toFixed(4)}`}` : "";
    renderCoachResponse(response, phase); renderProvenance(result.provenance); setStatus((language === "en" ? `AI Coach · ${safetyInterception ? "Health safety alert" : forcedFinish ? "Limited-data fallback" : usedTools ? "Extra history read" : "Memory loaded"}` : `AI 教练 · ${safetyInterception ? "健康安全提醒" : forcedFinish ? "已降级生成" : usedTools ? "已补充读取历史" : "记忆已加载"}`) + telemetry);
  } catch (error) {
    setStatus(language === "en" ? "AI service unavailable" : "AI 服务未连接", "error"); $("empty-plan").classList.add("hidden"); $("plan-content").classList.remove("hidden");
    const title = checkInSaved ? (language === "en" ? "Check-in saved, but AI guidance failed" : "打卡已保存，但 AI 建议生成失败") : (language === "en" ? "This check-in was not saved" : "这次没有保存");
    $("plan-content").innerHTML = `<div class="plan-intro"><strong>${escapeHtml(title)}</strong><br />${escapeHtml(error.message)}</div>`;
  } finally { button.disabled = false; button.innerHTML = original; }
}

$("morning-form").addEventListener("submit", (event) => {
  event.preventDefault();
  const height = Number($("profile-height").value);
  runPhase({ phase: "morning", button: $("morning-submit"), checkIn: { date: $("log-date").value, goal: $("goal").value, height, weight: $("weight").value, sleep: $("sleep").value, energy: $("energy").value, soreness: $("soreness").value, availableTime: $("available-time").value, notes: $("morning-notes").value.trim(), profileUpdate: { height, equipment: $("profile-equipment").value.trim(), dietaryPreferences: $("profile-diet").value.trim(), constraints: $("profile-constraints").value.trim() } } });
});

$("midday-form").addEventListener("submit", (event) => {
  event.preventDefault();
  syncPlanAdherenceFromExercises();
  const exercises = Array.from(document.querySelectorAll(".exercise-row")).map((row) => ({
    name: row.querySelector(".exercise-name").value.trim(),
    sets: row.querySelector(".exercise-sets").value,
    amount: row.querySelector(".exercise-amount").value,
    unit: row.querySelector(".exercise-unit").value,
    loadKg: row.querySelector(".exercise-load").value,
    completed: row.querySelector(".exercise-completed").checked,
    planIndex: row.dataset.planIndex === undefined ? null : Number(row.dataset.planIndex),
  })).filter((exercise) => exercise.name || exercise.amount);
  const totalDuration = exercises.filter((exercise) => exercise.completed && exercise.unit === "minutes").reduce((sum, exercise) => sum + (Number(exercise.sets) || 1) * (Number(exercise.amount) || 0), 0);
  runPhase({ phase: "midday", button: $("midday-submit"), checkIn: { date: $("log-date").value, exercises, totalDuration, planAdherence: $("plan-adherence").value, effort: $("workout-effort").value, notes: $("workout-notes").value.trim() } });
});

$("evening-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  try {
    const imageData = await Promise.all(photos.map(fileToDataUrl));
    runPhase({ phase: "evening", button: $("evening-submit"), images: imageData, checkIn: { date: $("log-date").value, food: $("food").value.trim(), bowelFrequency: $("bowel-frequency").value, bowelForm: $("bowel-form").value, bowelSymptoms: $("bowel-symptoms").value, notes: $("evening-notes").value.trim() } });
  } catch (error) { setStatus(error.message, "error"); }
});

$("log-date").addEventListener("change", () => {
  populateForms();
  loadExerciseProgress().catch((error) => setStatus(error.message, "error"));
});
$("clear-plan").addEventListener("click", showEmptyCoach);
switchPhase(activePhase, false);
applyLanguage();

fetch("/api/me", { credentials: "same-origin" }).then((response) => response.json()).then(async ({ user }) => {
  if (user) { showApp(user); await loadRecords(); }
}).catch(() => setStatus("记录服务未连接", "error"));
