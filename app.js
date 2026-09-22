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
  if (!response.ok) throw new Error(result.error || "操作失败");
  return result;
}

$("auth-toggle").addEventListener("click", () => {
  registerMode = !registerMode;
  $("auth-title").textContent = registerMode ? "注册" : "登录";
  $("auth-submit").textContent = registerMode ? "注册并登录" : "登录";
  $("auth-toggle").textContent = registerMode ? "已有账号？登录" : "还没有账号？注册";
  $("auth-password").autocomplete = registerMode ? "new-password" : "current-password";
  $("auth-error").textContent = "";
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
    : '<div class="upload-hint">点击选择照片，帮助 AI 识别分量和搭配</div>';
});

const fileToDataUrl = (file) => new Promise((resolve, reject) => {
  const reader = new FileReader();
  reader.onload = () => resolve(reader.result);
  reader.onerror = () => reject(new Error(`无法读取照片：${file.name}`));
  reader.readAsDataURL(file);
});

function renderPlan(plan) {
  $("empty-plan").classList.add("hidden");
  $("plan-content").classList.remove("hidden");
  $("plan-content").innerHTML = `<div class="plan-intro"><strong>明天的重点：${plan.title}</strong><br />${plan.summary}</div>
    <div class="plan-section"><span class="tag">${plan.training?.loadLabel || "个性化安排"}</span><h3>训练安排</h3><ul>${(plan.training?.items || []).map((item) => `<li>${item}</li>`).join("")}</ul></div>
    <div class="plan-section"><h3>饮食分析</h3><p>${plan.nutrition?.analysis || "暂无分析"}</p>${plan.nutrition?.estimatedCalories ? `<p>粗略估计：${plan.nutrition.estimatedCalories}</p>` : ""}</div>
    <div class="plan-section"><h3>明日饮食提醒</h3><p>${plan.nutrition?.nextDayTip || "保持均衡饮食和充足饮水。"}</p></div>
    <div class="plan-section"><h3>恢复与安全</h3><p>${plan.recovery || "训练时保持动作可控，不要在疼痛中训练。"}</p></div>
    ${plan.disclaimer ? `<p class="privacy-note">${plan.disclaimer}</p>` : ""}`;
  $("plan-title").textContent = plan.title;
}

function renderHistory() {
  $("record-count").textContent = `${records.length} 条记录`;
  $("history-list").innerHTML = records.length
    ? records.slice(0, 14).map((record) => `<div class="history-item"><div class="history-date">${record.date}</div><div class="history-summary">${record.weight ? `${record.weight} kg（${record.weightTiming === "evening" ? "晚餐后" : record.weightTiming === "morning" ? "晨起" : "其他"}） · ` : ""}${record.plan.title} · 精力 ${record.energy}/5 · 睡眠 ${record.sleep} 小时${record.plan.nutrition?.estimatedCalories ? ` · ${record.plan.nutrition.estimatedCalories}` : ""}</div></div>`).join("")
    : '<p class="muted">完成第一次打卡后，这里会显示你的记录。</p>';
}

function setStatus(text, state = "") {
  $("connection-status").className = `status-pill ${state}`;
  $("connection-status").innerHTML = `<span></span> ${text}`;
}

async function requestPlan(data, imageData) {
  const response = await fetch("/api/coach", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ checkIn: data, history: records.slice(0, 14), images: imageData })
  });
  const result = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(result.error || "AI 教练暂时无法响应");
  return result.plan;
}

async function saveRecord(record) {
  const response = await fetch("/api/records", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(record)
  });
  const result = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(result.error || "无法保存记录");
}

async function loadRecords() {
  const response = await fetch("/api/records", { credentials: "same-origin" });
  const result = await response.json().catch(() => ({}));
  if (response.status === 401) return;
  if (!response.ok) throw new Error(result.error || "无法读取历史记录");
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
  button.innerHTML = "AI 正在分析照片和训练历史…";
  setStatus("AI 分析中…", "loading");
  try {
    const imageData = await Promise.all(photos.map(fileToDataUrl));
    const plan = await requestPlan(data, imageData);
    const record = { ...data, plan };
    await saveRecord(record);
    records = [record, ...records.filter((item) => item.date !== data.date)];
    localStorage.setItem(storageKey, JSON.stringify(records));
    renderPlan(plan);
    renderHistory();
    setStatus("AI 教练 · 已连接");
  } catch (error) {
    setStatus("AI 服务未连接", "error");
    $("plan-content").classList.remove("hidden");
    $("empty-plan").classList.add("hidden");
    $("plan-title").textContent = "需要配置 AI";
    $("plan-content").innerHTML = `<div class="plan-intro"><strong>这次没有生成计划</strong><br />${error.message}</div><div class="plan-section"><p>请确认已启动后端，并在 <code>.env</code> 中设置 OPENAI_API_KEY。你的反馈没有被保存。</p></div>`;
  } finally {
    button.disabled = false;
    button.innerHTML = "让 AI 教练分析 <span>→</span>";
  }
});

$("clear-plan").addEventListener("click", () => {
  $("empty-plan").classList.remove("hidden");
  $("plan-content").classList.add("hidden");
  $("plan-content").innerHTML = "";
  $("plan-title").textContent = "明日计划";
});

fetch("/api/me", { credentials: "same-origin" }).then((response) => response.json()).then(async ({user}) => {
  if (user) {
    showApp(user);
    await loadRecords();
  }
}).catch(() => setStatus("记录服务未连接", "error"));
