/**
 * 首页 banner 天气小组件
 * 位置信息由后端通过 window.USER_CITY 注入（省 市 / 直辖市 / 未知）
 * 前端只负责：
 *   1. 用 open-meteo geocoding 把城市名解析为经纬度
 *   2. 用 open-meteo forecast 拿当前温度 + 天气代码
 * 纯前端，无 key。失败静默隐藏。
 */
(function () {
  'use strict';

  // WMO 天气代码 -> [FontAwesome 图标类, 中文描述]
  const WMO = {
    0:  ['fa-sun',                 '晴'],
    1:  ['fa-cloud-sun',           '晴间多云'],
    2:  ['fa-cloud-sun',           '多云'],
    3:  ['fa-cloud',               '阴'],
    45: ['fa-smog',                '雾'],
    48: ['fa-smog',                '雾凇'],
    51: ['fa-cloud-rain',          '毛毛雨'],
    53: ['fa-cloud-rain',          '小雨'],
    55: ['fa-cloud-rain',          '中雨'],
    56: ['fa-cloud-rain',          '冻雨'],
    57: ['fa-cloud-rain',          '冻雨'],
    61: ['fa-cloud-rain',          '小雨'],
    63: ['fa-cloud-rain',          '中雨'],
    65: ['fa-cloud-showers-heavy', '大雨'],
    66: ['fa-cloud-rain',          '冻雨'],
    67: ['fa-cloud-rain',          '冻雨'],
    71: ['fa-snowflake',           '小雪'],
    73: ['fa-snowflake',           '中雪'],
    75: ['fa-snowflake',           '大雪'],
    77: ['fa-snowflake',           '雪粒'],
    80: ['fa-cloud-showers-heavy', '阵雨'],
    81: ['fa-cloud-showers-heavy', '阵雨'],
    82: ['fa-cloud-showers-heavy', '强阵雨'],
    85: ['fa-snowflake',           '阵雪'],
    86: ['fa-snowflake',           '阵雪'],
    95: ['fa-bolt',                '雷阵雨'],
    96: ['fa-bolt',                '雷阵雨伴冰雹'],
    99: ['fa-bolt',                '雷阵雨伴冰雹'],
  };

  // 后端返回的“非城市名”一律视为无效
  const INVALID_CITIES = new Set(['未知', '内网', '本地', '']);

  const $ = (id) => document.getElementById(id);

  async function fetchJSON(url) {
    const r = await fetch(url, { cache: 'no-store' });
    if (!r.ok) throw new Error('HTTP ' + r.status);
    return r.json();
  }

  /**
   * 从后端传来的地名里提取用于 geocoding 的“城市名”
   *   "辽宁省 沈阳市"  -> "沈阳"
   *   "北京市"          -> "北京"
   *   "浙江省 杭州市"  -> "杭州"
   *   "新加坡"          -> "新加坡"
   */
  function extractCityName(raw) {
    if (!raw) return '';
    let name = String(raw).trim();
    if (!name) return '';

    // 取最后一段（“省 市”格式下就是市名）
    if (name.indexOf(' ') !== -1) {
      name = name.split(/\s+/).pop();
    }
    // 去掉常见行政区后缀，提高 geocoding 命中率
    name = name.replace(/[市县区]$/, '');
    return name;
  }

  async function loadWeather() {
    const widget = $('weatherWidget');
    if (!widget) return;

    const rawCity = (window.USER_CITY || '').trim();
    if (INVALID_CITIES.has(rawCity)) {
      // 后端没拿到有效属地，直接不显示
      return;
    }

    try {
      const cityName = extractCityName(rawCity);
      if (!cityName) return;

      // ---------- 1) 城市名 -> 经纬度 ----------
      const geo = await fetchJSON(
        'https://geocoding-api.open-meteo.com/v1/search' +
          '?name=' + encodeURIComponent(cityName) +
          '&language=zh' +
          '&count=1'
      );

      if (!geo || !Array.isArray(geo.results) || geo.results.length === 0) {
        // 城市查不到，静默放弃
        return;
      }

      const top = geo.results[0];
      const lat = top.latitude;
      const lon = top.longitude;
      // geocoding 拿到的中文名（比我们截出来的更准，例如“沈阳市”）
      const displayCity = top.name || cityName;

      // ---------- 2) 查当前天气 ----------
      const w = await fetchJSON(
        'https://api.open-meteo.com/v1/forecast' +
          '?latitude=' + lat +
          '&longitude=' + lon +
          '&current=temperature_2m,weather_code' +
          '&timezone=auto'
      );

      const cur = w.current || {};
      const info = WMO[cur.weather_code] || ['fa-cloud', '—'];
      const temp = Math.round(cur.temperature_2m);

      // ---------- 3) 渲染 ----------
      const iconEl = $('weatherIcon');
      const tempEl = $('weatherTemp');
      const descEl = $('weatherDesc');
      const cityEl = $('weatherCity');

      if (iconEl) iconEl.className = 'fas ' + info[0] + ' weather-icon';
      if (tempEl) tempEl.textContent = temp + '°C';
      if (descEl) descEl.textContent = info[1];
      if (cityEl) cityEl.textContent = displayCity ? '· ' + displayCity : '';

      widget.hidden = false;
    } catch (err) {
      // 静默失败，不影响页面
      console.warn('[weather] 加载失败：', err);
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', loadWeather);
  } else {
    loadWeather();
  }
})();