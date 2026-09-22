const $ = (id) => document.getElementById(id);
const storageKey = "fitness-coach-records";
const height = 158;
const today = new Date();
const isoDate = (date) => {
  const local = new Date(date.getTime() - date.getTimezoneOffset() * 60000);
  return local.toISOString().slice(0, 10);
};
$("log-date").value = isoDate(today);

let photos = [];
let records = [];
let currentUser = null;
let registerMode = false;
let language = localStorage.getItem("fitness-coach-language") || "zh";
let currentPlan = null;

const translations = {
  zh: {
    pageTitle: "我的健身教练",
    subtitle: "记录今天，获得更适合明天的训练建议。",
    statusWaiting: "AI 教练 · 等待配置",
    statusConnected: "AI 教练 · 已连接",
    statusAnalyzing: "AI 分析中…",
    statusDisconnected: "AI 服务未连接",
    statusRecords: "记录服务未连接",
    languageButton: "English",
    logout: "退出登录",
    account: "YOUR ACCOUNT",
    login: "登录",
    register: "注册",
    email: "邮箱",
    password: "密码（至少 8 位）",
    loginRegister: "注册并登录",
    existingAccount: "已有账号？登录",
    newAccount: "还没有账号？注册",
    checkIn: "TODAY'S CHECK-IN",
    todayFeedback: "今天的反馈",
    goal: "你的目标",
    fatLoss: "减脂塑形",
    muscle: "增肌增力",
    fitness: "提升体能",
    health: "保持健康",
    weight: "今天体重（kg）",
    weightPlaceholder: "例如：55.05",
    measurementTime: "测量时间",
    morning: "晨起空腹",
    evening: "晚餐后",
    other: "其他时间",
    weightHelp: "长期趋势请优先比较每天晨起、如厕、早餐前的体重；晚餐后的数据会单独标记。",
    food: "今天吃了什么？",
    foodPlaceholder: "例如：早餐鸡蛋和燕麦；午餐牛肉、米饭和西兰花……",
    foodStatus: "饮食记录状态",
    partial: "目前为止的部分记录",
    complete: "今天全天已完成",
    photos: "饮食照片",
    optional: "可选",
    photoHint: "点击选择照片，帮助 AI 识别分量和搭配",
    bowel: "排便情况",
    bowelHelp: "帮助教练调整纤维和饮水",
    frequency: "今天次数",
    none: "没有",
    one: "1 次",
    two: "2 次",
    three: "3 次或以上",
    bowelForm: "大便状态",
    normal: "正常",
    hard: "偏硬/干结",
    loose: "偏稀",
    watery: "水样",
    unknown: "不确定",
    symptoms: "排便感受",
    noDiscomfort: "无明显不适",
    straining: "需要用力",
    incomplete: "总觉得没排干净",
    bloating: "伴随腹胀",
    pain: "有疼痛/出血",
    bowelNote: "只记录你愿意分享的信息；持续疼痛、出血或明显异常请咨询医生。",
    workout: "今天完成的训练",
    workoutPlaceholder: "例如：深蹲 4×8、卧推 3×10，快走 20 分钟",
    energy: "精力",
    veryGood: "很好",
    good: "不错",
    average: "一般",
    low: "较低",
    veryLow: "很差",
    soreness: "肌肉酸痛",
    barely: "几乎没有",
    slight: "轻微",
    moderate: "中等",
    noticeable: "明显",
    severe: "很严重",
    sleep: "睡眠（小时）",
    notes: "特别想让教练注意什么？",
    notesPlaceholder: "例如：右膝有点不舒服，明天只有 30 分钟",
    analyze: "让 AI 教练分析",
    privacy: "提交后照片会发送到你配置的 AI 服务进行识别。不要上传敏感或可识别他人的照片。",
    response: "AI COACH RESPONSE",
    tomorrowPlan: "明日计划",
    clear: "清空",
    waiting: "等你来打卡",
    waitingText: "填写今天的状态后，我会根据你的目标、恢复情况和训练内容安排明天。",
    journey: "YOUR JOURNEY",
    history: "最近记录",
    records: "条记录",
    firstRecord: "完成第一次打卡后，这里会显示你的记录。",
    footer: "健康建议不能替代医生或持证教练的诊断。出现疼痛、胸闷、眩晕等症状时请停止训练并寻求专业帮助。",
    authFailed: "操作失败",
    aiFailed: "AI 教练暂时无法响应",
    saveFailed: "无法保存记录",
    loadFailed: "无法读取历史记录",
    needAi: "需要配置 AI",
    noPlan: "这次没有生成计划",
    configureAi: "请确认已启动后端，并在 .env 中设置 OPENAI_API_KEY。你的反馈没有被保存。",
    planFocus: "明天的重点：",
    training: "训练安排",
    nutrition: "饮食分析",
    nextDayFood: "明日饮食提醒",
    recovery: "恢复与安全",
    noAnalysis: "暂无分析",
    balanced: "保持均衡饮食和充足饮水。",
    safeTraining: "训练时保持动作可控，不要在疼痛中训练。",
    personalized: "个性化安排",
    morningShort: "晨起",
    afterDinner: "晚餐后",
    otherShort: "其他",
    energyShort: "精力",
    hours: "小时",
    cannotRead: "无法读取照片："
  },
  en: {
    pageTitle: "My Fitness Coach",
    subtitle: "Log today and get better training guidance for tomorrow.",
    statusWaiting: "AI Coach · Waiting for setup",
    statusConnected: "AI Coach · Connected",
    statusAnalyzing: "AI analysis in progress…",
    statusDisconnected: "AI service unavailable",
    statusRecords: "Record service unavailable",
    languageButton: "中文",
    logout: "Log out",
    account: "YOUR ACCOUNT",
    login: "Log in",
    register: "Sign up",
    email: "Email",
    password: "Password (at least 8 characters)",
    loginRegister: "Sign up and log in",
    existingAccount: "Already have an account? Log in",
    newAccount: "No account yet? Sign up",
    checkIn: "TODAY'S CHECK-IN",
    todayFeedback: "Today's check-in",
    goal: "Your goal",
    fatLoss: "Fat loss & shaping",
    muscle: "Build muscle & strength",
    fitness: "Improve fitness",
    health: "Stay healthy",
    weight: "Today's weight (kg)",
    weightPlaceholder: "e.g. 55.05",
    measurementTime: "Measurement time",
    morning: "Morning, fasted",
    evening: "After dinner",
    other: "Other time",
    weightHelp: "For long-term trends, compare morning weight after using the bathroom and before breakfast. Evening readings are marked separately.",
    food: "What did you eat today?",
    foodPlaceholder: "e.g. Eggs and oats for breakfast; beef, rice and broccoli for lunch…",
    foodStatus: "Food log status",
    partial: "Partial log so far",
    complete: "Full day completed",
    photos: "Food photos",
    optional: "Optional",
    photoHint: "Choose photos to help AI estimate portions and combinations",
    bowel: "Bowel movements",
    bowelHelp: "Helps your coach adjust fiber and hydration",
    frequency: "Today's count",
    none: "None",
    one: "1 time",
    two: "2 times",
    three: "3 or more times",
    bowelForm: "Stool consistency",
    normal: "Normal",
    hard: "Hard / dry",
    loose: "Loose",
    watery: "Watery",
    unknown: "Not sure",
    symptoms: "How it felt",
    noDiscomfort: "No noticeable discomfort",
    straining: "Needed to strain",
    incomplete: "Did not feel fully empty",
    bloating: "Bloating",
    pain: "Pain / bleeding",
    bowelNote: "Only share what you are comfortable sharing. Consult a doctor for persistent pain, bleeding or unusual symptoms.",
    workout: "Workout completed today",
    workoutPlaceholder: "e.g. Squats 4×8, bench press 3×10, brisk walk 20 minutes",
    energy: "Energy",
    veryGood: "Very good",
    good: "Good",
    average: "Average",
    low: "Low",
    veryLow: "Very low",
    soreness: "Muscle soreness",
    barely: "Almost none",
    slight: "Slight",
    moderate: "Moderate",
    noticeable: "Noticeable",
    severe: "Severe",
    sleep: "Sleep (hours)",
    notes: "Anything you want your coach to notice?",
    notesPlaceholder: "e.g. My right knee feels uncomfortable; I only have 30 minutes tomorrow",
    analyze: "Ask AI coach to analyze",
    privacy: "Photos will be sent to your configured AI service for analysis. Do not upload sensitive photos or photos identifying other people.",
    response: "AI COACH RESPONSE",
    tomorrowPlan: "Tomorrow's plan",
    clear: "Clear",
    waiting: "Ready when you are",
    waitingText: "After you fill in today's status, I will plan tomorrow based on your goals, recovery and training.",
    journey: "YOUR JOURNEY",
    history: "Recent records",
    records: "records",
    firstRecord: "Your records will appear here after your first check-in.",
    footer: "Health advice does not replace a diagnosis from a doctor or certified coach. Stop training and seek professional help if you experience pain, chest tightness or dizziness.",
    authFailed: "Operation failed",
    aiFailed: "The AI coach is temporarily unavailable",
    saveFailed: "Unable to save record",
    loadFailed: "Unable to load history",
    needAi: "AI setup required",
    noPlan: "No plan was generated",
    configureAi: "Please make sure the backend is running and OPENAI_API_KEY is configured in .env. Your check-in was not saved.",
    planFocus: "Tomorrow's focus: ",
    training: "Training plan",
    nutrition: "Nutrition analysis",
    nextDayFood: "Tomorrow's nutrition tip",
    recovery: "Recovery & safety",
    noAnalysis: "No analysis available",
    balanced: "Maintain a balanced diet and drink enough water.",
    safeTraining: "Keep movements controlled and never train through pain.",
    personalized: "Personalized plan",
    morningShort: "Morning",
    afterDinner: "After dinner",
    otherShort: "Other",
    energyShort: "Energy",
    hours: "hours",
    cannotRead: "Unable to read photo: "
  }
};

const t = (key) => translations[language][key] || translations.zh[key] || key;
const setText = (selector, key) => {
  const element = document.querySelector(selector);
  if (element) element.textContent = t(key);
};
const setFieldLabel = (id, key) => {
  const element = document.getElementById(id);
  const label = element?.closest("label");
  const span = label?.querySelector(":scope > span");
  if (span) span.textContent = t(key);
};
const setOptionalLabel = (selector, key) => {
  const span = document.querySelector(selector);
  if (span) {
    span.textContent = t(key);
    const optional = document.createElement("em");
    optional.textContent = t("optional");
    span.append(" ", optional);
  }
};
const setRadioLabel = (id, key) => {
  const label = document.getElementById(id);
  if (label) {
    const input = label.querySelector("input");
    label.textContent = "";
    label.append(input, ` ${t(key)}`);
  }
};

function applyLanguage() {
  document.documentElement.lang = language === "en" ? "en" : "zh-CN";
  document.title = t("pageTitle");
  setText("h1", "pageTitle");
  setText(".subtitle", "subtitle");
  setText("#language-toggle", "languageButton");
  setText("#logout-button", "logout");
  setText("#auth-card .section-kicker", "account");
  setText("#auth-title", registerMode ? "register" : "login");
  setFieldLabel("auth-email", "email");
  setFieldLabel("auth-password", "password");
  setText("#auth-submit", registerMode ? "loginRegister" : "login");
  setText("#auth-toggle", registerMode ? "existingAccount" : "newAccount");
  setText("#daily-form .section-kicker", "checkIn");
  setText("#daily-form h2", "todayFeedback");
  setFieldLabel("goal", "goal");
  [["fat-loss", "fatLoss"], ["muscle", "muscle"], ["fitness", "fitness"], ["health", "health"]].forEach(([value, key]) => setText(`#goal option[value="${value}"]`, key));
  setFieldLabel("weight", "weight");
  $("weight").placeholder = t("weightPlaceholder");
  setFieldLabel("weight-timing", "measurementTime");
  [["morning", "morning"], ["evening", "evening"], ["other", "other"]].forEach(([value, key]) => setText(`#weight-timing option[value="${value}"]`, key));
  setText("#weight-help", "weightHelp");
  setFieldLabel("food", "food");
  $("food").placeholder = t("foodPlaceholder");
  setText(".radio-field legend", "foodStatus");
  setRadioLabel("food-status-partial", "partial");
  setRadioLabel("food-status-complete", "complete");
  setOptionalLabel(".food-photo-label > span", "photos");
  setText("#food-photos + .photo-preview .upload-hint", "photoHint");
  setText(".wellness-heading span", "bowel");
  setText(".wellness-heading small", "bowelHelp");
  setFieldLabel("bowel-frequency", "frequency");
  [["0", "none"], ["1", "one"], ["2", "two"], ["3", "three"]].forEach(([value, key]) => setText(`#bowel-frequency option[value="${value}"]`, key));
  setFieldLabel("bowel-form", "bowelForm");
  [["normal", "normal"], ["hard", "hard"], ["loose", "loose"], ["watery", "watery"], ["unknown", "unknown"]].forEach(([value, key]) => setText(`#bowel-form option[value="${value}"]`, key));
  setFieldLabel("bowel-symptoms", "symptoms");
  [["none", "noDiscomfort"], ["straining", "straining"], ["incomplete", "incomplete"], ["bloating", "bloating"], ["pain", "pain"]].forEach(([value, key]) => setText(`#bowel-symptoms option[value="${value}"]`, key));
  setText("#bowel-help", "bowelNote");
  setFieldLabel("workout", "workout");
  $("workout").placeholder = t("workoutPlaceholder");
  setFieldLabel("energy", "energy");
  [["5", "veryGood"], ["4", "good"], ["3", "average"], ["2", "low"], ["1", "veryLow"]].forEach(([value, key]) => setText(`#energy option[value="${value}"]`, key));
  setFieldLabel("soreness", "soreness");
  [["1", "barely"], ["2", "slight"], ["3", "moderate"], ["4", "noticeable"], ["5", "severe"]].forEach(([value, key]) => setText(`#soreness option[value="${value}"]`, key));
  setFieldLabel("sleep", "sleep");
  setOptionalLabel(".notes-label > span", "notes");
  $("notes").placeholder = t("notesPlaceholder");
  $("submit-button").innerHTML = `${t("analyze")} <span>→</span>`;
  setText(".privacy-note", "privacy");
  setText(".plan-card .section-kicker", "response");
  setText("#plan-title", "tomorrowPlan");
  setText("#clear-plan", "clear");
  setText("#empty-plan h3", "waiting");
  setText("#empty-plan p", "waitingText");
  setText("#history-content .section-kicker", "journey");
  setText("#history-content h2", "history");
  setText("#record-count", `${records.length} ${t("records")}`);
  setText("#history-list .muted", "firstRecord");
  setText("#app-footer", "footer");
  if ($("connection-status").classList.contains("loading")) setStatus(t("statusAnalyzing"), "loading");
}

$("language-toggle").addEventListener("click", () => {
  language = language === "zh" ? "en" : "zh";
  localStorage.setItem("fitness-coach-language", language);
  applyLanguage();
  renderHistory();
  if (currentPlan) renderPlan(currentPlan);
});

function showApp(user) {
  currentUser = user;
  $("auth-card").classList.toggle("hidden", !!user);
  $("app-content").classList.toggle("hidden", !user);
  $("history-content").classList.toggle("hidden", !user);
  $("app-footer").classList.toggle("hidden", !user);
  $("logout-button").classList.toggle("hidden", !user);
  if (user) $("auth-user").textContent = user.email;
}

async function authRequest(path, body) {
  const response = await fetch(path, { method: "POST", headers: {"Content-Type": "application/json"}, credentials: "same-origin", body: JSON.stringify(body) });
  const result = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(result.error || t("authFailed"));
  return result;
}

$("auth-toggle").addEventListener("click", () => {
  registerMode = !registerMode;
  $("auth-password").autocomplete = registerMode ? "new-password" : "current-password";
  $("auth-error").textContent = "";
  applyLanguage();
});

$("auth-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  $("auth-error").textContent = "";
  try {
    const result = await authRequest(registerMode ? "/api/register" : "/api/login", {
      email: $("auth-email").value, password: $("auth-password").value
    });
    showApp(result.user);
    await loadRecords();
  } catch (error) {
    $("auth-error").textContent = error.message;
  }
});

$("logout-button").addEventListener("click", async () => {
  await authRequest("/api/logout", {});
  records = [];
  renderHistory();
  showApp(null);
});

$("food-photos").addEventListener("change", (event) => {
  photos = Array.from(event.target.files || []);
  $("photo-preview").innerHTML = photos.length
    ? photos.map((photo) => `<img src="${URL.createObjectURL(photo)}" alt="饮食照片" />`).join("")
    : `<div class="upload-hint">${t("photoHint")}</div>`;
});

const fileToDataUrl = (file) => new Promise((resolve, reject) => {
  const reader = new FileReader();
  reader.onload = () => resolve(reader.result);
  reader.onerror = () => reject(new Error(`${t("cannotRead")}${file.name}`));
  reader.readAsDataURL(file);
});

function renderPlan(plan) {
  currentPlan = plan;
  $("empty-plan").classList.add("hidden");
  $("plan-content").classList.remove("hidden");
  $("plan-content").innerHTML = `<div class="plan-intro"><strong>明天的重点：${plan.title}</strong><br />${plan.summary}</div>
    <div class="plan-section"><span class="tag">${plan.training?.loadLabel || t("personalized")}</span><h3>${t("training")}</h3><ul>${(plan.training?.items || []).map((item) => `<li>${item}</li>`).join("")}</ul></div>
    <div class="plan-section"><h3>${t("nutrition")}</h3><p>${plan.nutrition?.analysis || t("noAnalysis")}</p>${plan.nutrition?.estimatedCalories ? `<p>${language === "en" ? "Estimated:" : "粗略估计："} ${plan.nutrition.estimatedCalories}</p>` : ""}</div>
    <div class="plan-section"><h3>${t("nextDayFood")}</h3><p>${plan.nutrition?.nextDayTip || t("balanced")}</p></div>
    <div class="plan-section"><h3>${t("recovery")}</h3><p>${plan.recovery || t("safeTraining")}</p></div>
    ${plan.disclaimer ? `<p class="privacy-note">${plan.disclaimer}</p>` : ""}`;
  $("plan-title").textContent = plan.title;
}

function renderHistory() {
  $("record-count").textContent = `${records.length} ${t("records")}`;
  $("history-list").innerHTML = records.length
    ? records.slice(0, 14).map((record) => `<div class="history-item"><div class="history-date">${record.date}</div><div class="history-summary">${record.weight ? `${record.weight} kg (${record.weightTiming === "evening" ? t("afterDinner") : record.weightTiming === "morning" ? t("morningShort") : t("otherShort")}) · ` : ""}${record.plan.title} · ${t("energyShort")} ${record.energy}/5 · ${record.sleep} ${t("hours")}${record.plan.nutrition?.estimatedCalories ? ` · ${record.plan.nutrition.estimatedCalories}` : ""}</div></div>`).join("")
    : `<p class="muted">${t("firstRecord")}</p>`;
}

function setStatus(text, state = "") {
  $("connection-status").className = `status-pill ${state}`;
  $("connection-status").innerHTML = `<span></span> ${text}`;
}

async function requestPlan(data, imageData) {
  const response = await fetch("/api/coach", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ checkIn: data, history: records.slice(0, 14), images: imageData, language })
  });
  const result = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(result.error || t("aiFailed"));
  return result.plan;
}

async function saveRecord(record) {
  const response = await fetch("/api/records", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(record)
  });
  const result = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(result.error || t("saveFailed"));
}

async function loadRecords() {
  const response = await fetch("/api/records", { credentials: "same-origin" });
  const result = await response.json().catch(() => ({}));
  if (response.status === 401) return;
  if (!response.ok) throw new Error(result.error || t("loadFailed"));
  records = Array.isArray(result.records) ? result.records : [];
  renderHistory();
}

$("daily-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const button = $("submit-button");
  const data = {
    date: $("log-date").value, goal: $("goal").value, height,
    weight: $("weight").value, weightTiming: $("weight-timing").value,
    food: $("food").value.trim(),
    foodStatus: document.querySelector('input[name="food-status"]:checked').value,
    bowelFrequency: $("bowel-frequency").value, bowelForm: $("bowel-form").value,
    bowelSymptoms: $("bowel-symptoms").value,
    workout: $("workout").value.trim(), energy: $("energy").value, soreness: $("soreness").value,
    sleep: $("sleep").value, notes: $("notes").value.trim()
  };
  button.disabled = true;
  button.innerHTML = `${t("statusAnalyzing")} <span>…</span>`;
  setStatus(t("statusAnalyzing"), "loading");
  try {
    const imageData = await Promise.all(photos.map(fileToDataUrl));
    const plan = await requestPlan(data, imageData);
    const record = { ...data, plan };
    await saveRecord(record);
    records = [record, ...records.filter((item) => item.date !== data.date)];
    localStorage.setItem(storageKey, JSON.stringify(records));
    renderPlan(plan);
    renderHistory();
    setStatus(t("statusConnected"));
  } catch (error) {
    setStatus(t("statusDisconnected"), "error");
    $("plan-content").classList.remove("hidden");
    $("empty-plan").classList.add("hidden");
    $("plan-title").textContent = t("needAi");
    $("plan-content").innerHTML = `<div class="plan-intro"><strong>${t("noPlan")}</strong><br />${error.message}</div><div class="plan-section"><p>${t("configureAi")}</p></div>`;
  } finally {
    button.disabled = false;
    button.innerHTML = `${t("analyze")} <span>→</span>`;
  }
});

$("clear-plan").addEventListener("click", () => {
  $("empty-plan").classList.remove("hidden");
  $("plan-content").classList.add("hidden");
  $("plan-content").innerHTML = "";
  $("plan-title").textContent = t("tomorrowPlan");
});

applyLanguage();

fetch("/api/me", { credentials: "same-origin" }).then((response) => response.json()).then(async ({user}) => {
  if (user) {
    showApp(user);
    await loadRecords();
  }
}).catch(() => setStatus(t("statusRecords"), "error"));
