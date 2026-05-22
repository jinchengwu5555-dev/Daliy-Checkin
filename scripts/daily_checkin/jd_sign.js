const axios = require('axios');

// 青龙面板从环境变量读取 Cookie
// 支持多账号，用 & 或 \n 分隔
const cookieStr = process.env.JD_COOKIE || '';

if (!cookieStr.trim()) {
  console.log('🛒 京东');
  console.log('❌ 签到失败: 未设置 JD_COOKIE');
  process.exit(0);
}

// 多账号拆分
const cookies = cookieStr
  .split(/\n|&/)
  .map(c => c.trim())
  .filter(Boolean);

async function sign(cookie, index) {
  const accountTag = cookies.length > 1 ? `账号 ${index + 1}` : '';
  console.log(`\n🛒 京东${accountTag ? ' - ' + accountTag : ''}`);

  try {
    const res = await axios.post(
      'https://api.m.jd.com/client.action',
      'functionId=signBeanAct&appid=ld&body=%7B%22rnVersion%22%3A%228.1.0%22%2C%22channel%22%3A1%2C%22os%22%3A%22apple%22%2C%22enAli%22%3A%221%22%7D',
      {
        headers: {
          'Cookie': cookie,
          'User-Agent': 'JDMobileIOS/13.0.2 (iPhone; iOS 16.0; Scale/3.00)',
          'Content-Type': 'application/x-www-form-urlencoded',
          'Referer': 'https://bean.m.jd.com/',
          'Host': 'api.m.jd.com'
        },
        timeout: 10000
      }
    );

    const d = res.data?.data;

    if (!d) {
      console.log('⚠️ 接口返回异常:', JSON.stringify(res.data));
      return;
    }

    const status = String(d.status);

    if (status === '1') {
      const beans = d.dailyAward?.beanAward?.beanCount
        || d.signInfo?.signScore
        || 0;
      console.log(`✅ 签到成功: +${beans} 京豆`);
      if (d.continuousDays) {
        console.log(`📅 连续签到: ${d.continuousDays} 天`);
      }
    } else if (status === '2') {
      console.log('ℹ️ 今日已签到');
    } else if (status === '3') {
      console.log('❌ 签到失败: Cookie 已过期，请重新获取');
    } else {
      console.log(`⚠️ 未知状态: ${d.status ?? 'null'}`);
      console.log('原始响应:', JSON.stringify(d));
    }

  } catch (e) {
    console.log('❌ 签到失败:', e.message);
  }
}

(async () => {
  for (let i = 0; i < cookies.length; i++) {
    await sign(cookies[i], i);
    // 多账号间隔，避免触发风控
    if (i < cookies.length - 1) {
      await new Promise(r => setTimeout(r, 2000));
    }
  }
})();
