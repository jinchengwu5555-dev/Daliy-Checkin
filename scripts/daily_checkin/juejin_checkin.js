#!/usr/bin/env node
// 掘金签到
// cron: 0 7 * * *
// new Env('掘金签到');

const axios = require('axios');

const cookies = process.env.JUEJIN_COOKIES ? process.env.JUEJIN_COOKIES.split('#') : [];
const AID_APP = "1931", AID_WEB = "2608";
const generateUUID = () => "71439" + Math.floor(Math.random() * 1000000000);

async function executeTask(cookie, index) {
  const uuid = generateUUID();
  const APP_PARAMS = `?aid=${AID_APP}&uuid=${uuid}&app_name=juejin_sdk&device_platform=android`;
  const WEB_PARAMS = `?aid=${AID_WEB}&uuid=${uuid}`;
  const api = axios.create({
    baseURL: 'https://api.juejin.cn',
    timeout: 15000,
    headers: {
      'Cookie': cookie,
      'User-Agent': 'Mozilla/5.0 (Linux; Android 12; SM-G991B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Mobile Safari/537.36 Juejin/Android/6.0.1',
      'Content-Type': 'application/json'
    }
  });

  console.log(`\n========== 账号 ${index + 1} ==========`);

  try {
    const userRes = await api.get("/user_api/v1/user/get" + WEB_PARAMS);
    console.log("用户: " + (userRes.data?.data?.user_name || "未知"));

    // 签到
    const ck = await api.post("/growth_api/v1/check_in" + APP_PARAMS, {});
    if (ck.data?.err_no === 0) {
      console.log("✅ 签到成功: +" + ck.data.data.incr_point + " 矿石");
    } else if (ck.data?.err_no === 20001 || ck.data?.err_msg?.includes("已完成")) {
      console.log("ℹ️ 今日已签到");
    } else {
      console.log("❌ 签到失败: " + (ck.data?.err_msg || "未知错误"));
    }

    // 沾喜气
    try {
      const history = await api.post("/growth_api/v1/lottery_history/global_big" + WEB_PARAMS, { page_no: 1, page_size: 5 });
      const luckyId = history.data?.data?.lotteries?.[0]?.history_id || "7143943034230636551";
      const dip = await api.post("/growth_api/v1/lottery_lucky/dip_lucky" + APP_PARAMS, { lottery_history_id: luckyId });
      if (dip.data?.err_no === 0) {
        console.log("✅ 沾喜气成功: +" + dip.data.data.dip_value + " 幸运值");
      } else {
        console.log("ℹ️ 沾喜气: 今日已沾");
      }
    } catch {
      console.log("⚠️ 沾喜气异常");
    }

    // 抽奖
    const cfg = await api.get("/growth_api/v1/lottery_config/get" + APP_PARAMS);
    if (cfg.data?.data?.free_count > 0) {
      const draw = await api.post("/growth_api/v1/lottery/draw" + APP_PARAMS, {});
      if (draw.data?.err_no === 0) {
        console.log("✅ 抽奖成功: " + draw.data.data.lottery_name);
      } else {
        console.log("❌ 抽奖失败");
      }
    } else {
      console.log("ℹ️ 今日无免费抽奖");
    }

    // 统计
    const counts = await api.get("/growth_api/v1/get_counts" + WEB_PARAMS);
    const pts = await api.get("/growth_api/v1/get_cur_point" + WEB_PARAMS);
    if (counts.data?.data) {
      console.log(`连续签到: ${counts.data.data.cont_count} 天 | 累计: ${counts.data.data.sum_count} 天`);
    }
    if (pts.data) console.log("当前矿石: " + pts.data.data);

  } catch (e) {
    console.log("⚠️ 异常: " + e.message);
  }
}

async function main() {
  if (!cookies.length) {
    console.log("❌ 签到失败: 未设置 JUEJIN_COOKIES");
    process.exit(1);
  }
  for (let i = 0; i < cookies.length; i++) {
    await executeTask(cookies[i], i);
  }
  console.log("\n========== 运行完毕 ==========");
}

main();
