const axios = require('axios');

const cookieStr = process.env.JD_COOKIE || '';

if (!cookieStr.trim()) {
  console.log('🛒 京东');
  console.log('❌ 签到失败: 未设置 JD_COOKIE');
  process.exit(0);
}

const cookies = cookieStr
  .split(/\n|&/)
  .map(c => c.trim())
  .filter(Boolean);

// 尝试不同的签到接口
const ENDPOINTS = [
  {
    url: 'https://api.m.jd.com/client.action',
    body: 'functionId=signBeanAct&appid=ld&body=%7B%22rnVersion%22%3A%228.2.0%22%2C%22channel%22%3A1%2C%22os%22%3A%22apple%22%2C%22enAli%22%3A%221%22%7D&client=apple&clientVersion=13.2.0',
    name: 'signBeanAct',
  },
  {
    url: 'https://api.m.jd.com/client.action',
    body: 'functionId=appsignindex&appid=signed_wh5&body=%7B%22rnVersion%22%3A%228.2.0%22%2C%22channel%22%3A1%2C%22os%22%3A%22apple%22%2C%22enAli%22%3A%221%22%7D&client=wh5&clientVersion=1.0.0',
    name: 'appsignindex',
  },
];

function parseResult(d, endpointName) {
  if (!d) return null;

  // signBeanAct 响应格式
  if (d.status !== undefined) {
    const status = String(d.status);
    if (status === '1') {
      const beans = d.dailyAward?.beanAward?.beanCount
        || d.signInfo?.signScore
        || d.beanCount
        || 0;
      return { ok: true, msg: `✅ 签到成功: +${beans} 京豆${d.continuousDays ? `，连续 ${d.continuousDays} 天` : ''}` };
    }
    if (status === '2') return { ok: true, msg: 'ℹ️ 今日已签到' };
    if (status === '3') return { ok: false, msg: '❌ Cookie 已过期，请重新获取' };
  }

  // appsignindex 或其他格式：检查 resultCode / code
  const code = String(d.resultCode ?? d.code ?? '');
  if (code === '0' || code === '200') {
    return { ok: true, msg: `✅ 签到成功 (${endpointName})` };
  }
  if (d.signResult === true || d.signed === true) {
    return { ok: true, msg: `✅ 签到成功 (${endpointName})` };
  }

  return null; // 无法识别，返回 null 让上层打印原始响应
}

async function sign(cookie, index) {
  const accountTag = cookies.length > 1 ? ` - 账号 ${index + 1}` : '';
  console.log(`\n🛒 京东${accountTag}`);

  for (const ep of ENDPOINTS) {
    try {
      const res = await axios.post(ep.url, ep.body, {
        headers: {
          'Cookie': cookie,
          'User-Agent': 'JDMobileIOS/13.2.0 (iPhone; iOS 16.7; Scale/3.00)',
          'Content-Type': 'application/x-www-form-urlencoded',
          'Referer': 'https://bean.m.jd.com/',
          'Host': 'api.m.jd.com',
        },
        timeout: 10000,
      });

      const raw = res.data;
      const d = raw?.data ?? raw;

      const parsed = parseResult(d, ep.name);
      if (parsed) {
        console.log(parsed.msg);
        return; // 成功解析则不再尝试下一个端点
      }

      // 返回了数据但无法解析 — 打印原始响应后继续尝试下一接口
      console.log(`⚠️ [${ep.name}] 响应未识别: ${JSON.stringify(raw).slice(0, 300)}`);
    } catch (e) {
      console.log(`❌ [${ep.name}] 请求失败: ${e.message}`);
    }
  }

  console.log('❌ 所有接口均未签到成功，请检查 Cookie 或 API 是否变更');
}

(async () => {
  for (let i = 0; i < cookies.length; i++) {
    await sign(cookies[i], i);
    if (i < cookies.length - 1) {
      await new Promise(r => setTimeout(r, 2000));
    }
  }
})();
