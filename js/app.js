/**
 * 主应用逻辑 - 新UI版本
 */

// 全局状态
let appData = {
    lotteryHistory: null,
    aiPredictions: null,
    predictionsHistory: null
};

// 初始化应用
async function initApp() {
    try {
        // 加载数据
        await loadAllData();

        // 渲染UI
        renderHeroBanner();
        renderModelsGrid();
        renderHistoryTab();

        // 设置事件监听
        setupEventListeners();

        // 隐藏加载屏幕
        hideLoadingScreen();
    } catch (error) {
        console.error('初始化失败:', error);
        alert('数据加载失败，请刷新页面重试');
    }
}

// 加载所有数据
async function loadAllData() {
    try {
        const [lotteryHistory, aiPredictions, predictionsHistory] = await Promise.all([
            DataLoader.loadLotteryHistory(),
            DataLoader.loadPredictions(),
            DataLoader.loadPredictionsHistory()
        ]);

        appData.lotteryHistory = lotteryHistory;
        appData.aiPredictions = aiPredictions;
        appData.predictionsHistory = predictionsHistory;
    } catch (error) {
        console.error('数据加载失败:', error);
        throw error;
    }
}

// 渲染Hero Banner
function renderHeroBanner() {
    if (!appData.lotteryHistory || !appData.aiPredictions) return;

    const nextDraw = appData.lotteryHistory.next_draw;

    // 更新期号
    const heroPeriodEl = document.getElementById('heroPeriod');
    if (heroPeriodEl) heroPeriodEl.textContent = nextDraw.next_period;

    // 更新日期显示
    const heroDateDisplayEl = document.getElementById('heroDateDisplay');
    if (heroDateDisplayEl) heroDateDisplayEl.textContent = nextDraw.next_date_display;

    // 更新开奖时间
    const heroDrawTimeEl = document.getElementById('heroDrawTime');
    if (heroDrawTimeEl) heroDrawTimeEl.textContent = `${nextDraw.draw_time} 开奖`;

    // 更新预测日期
    const heroPredictionDateEl = document.getElementById('heroPredictionDate');
    if (heroPredictionDateEl) heroPredictionDateEl.textContent = appData.aiPredictions.prediction_date;

    // 倒计时 (可选功能)
    const heroCountdownEl = document.getElementById('heroCountdown');
    if (heroCountdownEl) {
        const daysUntil = calculateDaysUntil(nextDraw.next_date);
        heroCountdownEl.textContent = daysUntil > 0 ? `距离开奖仅剩 ${daysUntil} 天` : '即将开奖';
    }
}

// 渲染模型网格
function renderModelsGrid() {
    if (!appData.aiPredictions) return;

    const modelsGridEl = document.getElementById('modelsGrid');
    if (!modelsGridEl) return;

    // 清空现有内容
    modelsGridEl.innerHTML = '';

    // 检测预测期号是否已开奖
    const targetPeriod = appData.aiPredictions.target_period;
    const latestDraw = appData.lotteryHistory?.data?.[0];
    let actualResult = null;

    if (latestDraw && parseInt(targetPeriod) <= parseInt(latestDraw.period)) {
        // 预测期号已开奖，查找对应的开奖结果
        actualResult = appData.lotteryHistory.data.find(draw => draw.period === targetPeriod);

        if (actualResult) {
            // 在网格前添加状态提示
            const statusBanner = createDrawnStatusBanner(actualResult);
            modelsGridEl.appendChild(statusBanner);
        }
    }

    // 渲染每个模型
    appData.aiPredictions.models.forEach(model => {
        const modelCard = Components.createModelCard(model, actualResult);
        modelsGridEl.appendChild(modelCard);
    });
}

// 创建已开奖状态横幅
function createDrawnStatusBanner(actualResult) {
    const banner = document.createElement('div');
    banner.className = 'drawn-status-banner';
    banner.innerHTML = `
        <div class="drawn-status-icon">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/>
                <polyline points="22 4 12 14.01 9 11.01"/>
            </svg>
        </div>
        <div class="drawn-status-content">
            <h3 class="drawn-status-title">第 ${actualResult.period} 期已开奖</h3>
            <p class="drawn-status-subtitle">以下为预测命中情况对比</p>
        </div>
        <div class="drawn-status-balls">
            ${actualResult.red_balls.map(num => `<span class="mini-result-ball red">${num}</span>`).join('')}
            <span class="mini-result-ball blue">${actualResult.blue_ball}</span>
        </div>
    `;
    return banner;
}

// 渲染历史标签页
function renderHistoryTab() {
    // 渲染准确度图表
    renderAccuracyChart();

    // 渲染准确度卡片
    renderAccuracyCards();

    // 渲染历史表格
    renderHistoryTable();
}

// 渲染准确度图表
function renderAccuracyChart() {
    if (!appData.predictionsHistory) return;

    const chartEl = document.getElementById('accuracyChart');
    if (!chartEl) return;

    // 准备图表数据
    const chartData = prepareChartData();

    // 使用Chart.js渲染
    new Chart(chartEl, {
        type: 'line',
        data: {
            labels: chartData.labels,
            datasets: chartData.datasets
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    position: 'top',
                },
                tooltip: {
                    mode: 'index',
                    intersect: false,
                }
            },
            scales: {
                y: {
                    beginAtZero: true,
                    max: 7,
                    ticks: {
                        stepSize: 1
                    },
                    title: {
                        display: true,
                        text: '命中球数'
                    }
                }
            }
        }
    });
}

// 准备图表数据
function prepareChartData() {
    const history = appData.predictionsHistory.predictions_history;

    // 反转以显示时间顺序
    const reversedHistory = [...history].reverse();
    const labels = reversedHistory.map(record => record.target_period);
    const series = new Map();

    reversedHistory.forEach((record, periodIndex) => {
        const isSimulation = record.data_source === 'random_simulation';
        record.models.forEach(model => {
            const key = JSON.stringify([isSimulation, model.model_name]);
            if (!series.has(key)) {
                series.set(key, {
                    modelName: model.model_name,
                    isSimulation,
                    data: Array(labels.length).fill(null)
                });
            }

            // 按期号对齐；缺失期保持空值，随机模拟不计入 AI 模型表现。
            const bestHit = Math.max(...model.predictions.map(p => p.hit_result?.total_hits || 0));
            series.get(key).data[periodIndex] = bestHit;
        });
    });

    // 转换为Chart.js数据集格式
    const colors = {
        'GPT-5': '#10b981',
        'Claude 4.5': '#8b5cf6',
        'Gemini 2.5': '#3b82f6',
        'DeepSeek R1': '#f59e0b'
    };

    const datasets = [...series.values()].map(({ modelName, isSimulation, data }) => ({
        label: isSimulation ? `${modelName}（非实测）` : modelName,
        data,
        borderColor: isSimulation ? '#6b7280' : colors[modelName] || '#6b7280',
        backgroundColor: isSimulation ? '#6b7280' : colors[modelName] || '#6b7280',
        borderDash: isSimulation ? [6, 4] : [],
        spanGaps: false,
        borderWidth: 3,
        pointRadius: 4,
        pointHoverRadius: 7,
        tension: 0.1
    }));

    return { labels, datasets };
}

// 渲染准确度卡片
function renderAccuracyCards() {
    if (!appData.predictionsHistory) return;

    const containerEl = document.getElementById('accuracyCardsContainer');
    if (!containerEl) return;

    // 清空现有内容
    containerEl.innerHTML = '';

    // 渲染每个记录
    appData.predictionsHistory.predictions_history.forEach(record => {
        const card = Components.createAccuracyCard(record);
        containerEl.appendChild(card);
    });
}

// 渲染历史表格
function renderHistoryTable() {
    if (!appData.lotteryHistory) return;

    const tableBodyEl = document.getElementById('historyTableBody');
    if (!tableBodyEl) return;

    // 清空现有内容
    tableBodyEl.innerHTML = '';

    // 渲染每一行
    appData.lotteryHistory.data.forEach(draw => {
        const row = Components.createHistoryTableRow(draw);
        tableBodyEl.appendChild(row);
    });
}

// 渲染频率图表 (分析标签页)
function renderFrequencyChart() {
    if (!appData.lotteryHistory) return;

    const chartEl = document.getElementById('frequencyChart');
    if (!chartEl) return;

    // 计算红球频率
    const frequency = {};
    for (let i = 1; i <= 33; i++) {
        frequency[i.toString().padStart(2, '0')] = 0;
    }

    appData.lotteryHistory.data.forEach(draw => {
        draw.red_balls.forEach(ball => {
            frequency[ball] = (frequency[ball] || 0) + 1;
        });
    });

    const labels = Object.keys(frequency).sort();
    const data = labels.map(label => frequency[label]);

    // 使用Chart.js渲染
    new Chart(chartEl, {
        type: 'bar',
        data: {
            labels: labels,
            datasets: [{
                label: '出现次数',
                data: data,
                backgroundColor: '#fca5a5',
                borderRadius: 4
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    display: false
                }
            },
            scales: {
                y: {
                    beginAtZero: true,
                    ticks: {
                        stepSize: 1
                    }
                }
            }
        }
    });
}

// 渲染统计卡片
function renderStatisticsCards() {
    if (!appData.lotteryHistory) return;

    // 计算红球频率
    const redFrequency = {};
    for (let i = 1; i <= 33; i++) {
        redFrequency[i.toString().padStart(2, '0')] = 0;
    }

    // 计算蓝球频率
    const blueFrequency = {};
    for (let i = 1; i <= 16; i++) {
        blueFrequency[i.toString().padStart(2, '0')] = 0;
    }

    // 计算和值
    let totalSum = 0;

    appData.lotteryHistory.data.forEach(draw => {
        // 红球
        draw.red_balls.forEach(ball => {
            redFrequency[ball] = (redFrequency[ball] || 0) + 1;
        });
        // 蓝球
        blueFrequency[draw.blue_ball] = (blueFrequency[draw.blue_ball] || 0) + 1;
        // 和值
        const sum = draw.red_balls.reduce((acc, ball) => acc + parseInt(ball), 0);
        totalSum += sum;
    });

    // 找出最热红球
    const hottestRed = Object.entries(redFrequency).sort((a, b) => b[1] - a[1])[0];

    // 找出最热蓝球
    const hottestBlue = Object.entries(blueFrequency).sort((a, b) => b[1] - a[1])[0];

    // 平均和值
    const avgSum = Math.round(totalSum / appData.lotteryHistory.data.length);

    // 更新UI
    const totalDrawsEl = document.getElementById('statTotalDraws');
    if (totalDrawsEl) totalDrawsEl.textContent = `${appData.lotteryHistory.data.length} 期`;

    const hottestRedEl = document.getElementById('statHottestRed');
    if (hottestRedEl) hottestRedEl.textContent = `${hottestRed[0]} (${hottestRed[1]}次)`;

    const hottestBlueEl = document.getElementById('statHottestBlue');
    if (hottestBlueEl) hottestBlueEl.textContent = `${hottestBlue[0]} (${hottestBlue[1]}次)`;

    const avgSumEl = document.getElementById('statAvgSum');
    if (avgSumEl) avgSumEl.textContent = avgSum;
}

// 渲染蓝球频率图表
function renderBlueFrequencyChart() {
    if (!appData.lotteryHistory) return;

    const chartEl = document.getElementById('blueFrequencyChart');
    if (!chartEl) return;

    // 计算蓝球频率
    const frequency = {};
    for (let i = 1; i <= 16; i++) {
        frequency[i.toString().padStart(2, '0')] = 0;
    }

    appData.lotteryHistory.data.forEach(draw => {
        frequency[draw.blue_ball] = (frequency[draw.blue_ball] || 0) + 1;
    });

    const labels = Object.keys(frequency).sort();
    const data = labels.map(label => frequency[label]);

    // 使用Chart.js渲染
    new Chart(chartEl, {
        type: 'bar',
        data: {
            labels: labels,
            datasets: [{
                label: '出现次数',
                data: data,
                backgroundColor: '#93c5fd',
                borderRadius: 4
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    display: false
                }
            },
            scales: {
                y: {
                    beginAtZero: true,
                    ticks: {
                        stepSize: 1
                    }
                }
            }
        }
    });
}

// 渲染奇偶比图表
function renderOddEvenChart() {
    if (!appData.lotteryHistory) return;

    const chartEl = document.getElementById('oddEvenChart');
    if (!chartEl) return;

    // 计算奇偶比分布
    const ratioCount = {};

    appData.lotteryHistory.data.forEach(draw => {
        const oddCount = draw.red_balls.filter(ball => parseInt(ball) % 2 === 1).length;
        const evenCount = 6 - oddCount;
        const ratio = `${oddCount}:${evenCount}`;
        ratioCount[ratio] = (ratioCount[ratio] || 0) + 1;
    });

    // 按常见比例排序
    const commonRatios = ['0:6', '1:5', '2:4', '3:3', '4:2', '5:1', '6:0'];
    const labels = commonRatios.filter(r => ratioCount[r]);
    const data = labels.map(label => ratioCount[label] || 0);

    // 使用Chart.js渲染
    new Chart(chartEl, {
        type: 'doughnut',
        data: {
            labels: labels.map(l => `${l} (奇:偶)`),
            datasets: [{
                data: data,
                backgroundColor: [
                    '#ef4444', '#f97316', '#f59e0b',
                    '#10b981', '#3b82f6', '#8b5cf6', '#ec4899'
                ],
                borderWidth: 2,
                borderColor: '#fff'
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    position: 'bottom',
                    labels: {
                        padding: 15,
                        font: {
                            size: 11
                        }
                    }
                }
            }
        }
    });
}

// 渲染和值走势图表
function renderSumTrendChart() {
    if (!appData.lotteryHistory) return;

    const chartEl = document.getElementById('sumTrendChart');
    if (!chartEl) return;

    // 取最近30期
    const recentDraws = appData.lotteryHistory.data.slice(0, 30).reverse();

    const labels = recentDraws.map(draw => draw.period);
    const sums = recentDraws.map(draw =>
        draw.red_balls.reduce((acc, ball) => acc + parseInt(ball), 0)
    );

    // 计算平均线
    const avgSum = sums.reduce((a, b) => a + b, 0) / sums.length;

    // 使用Chart.js渲染
    new Chart(chartEl, {
        type: 'line',
        data: {
            labels: labels,
            datasets: [
                {
                    label: '红球和值',
                    data: sums,
                    borderColor: '#ef4444',
                    backgroundColor: 'rgba(239, 68, 68, 0.1)',
                    borderWidth: 3,
                    pointRadius: 4,
                    pointHoverRadius: 7,
                    tension: 0.3,
                    fill: true
                },
                {
                    label: '平均值',
                    data: Array(sums.length).fill(avgSum),
                    borderColor: '#94a3b8',
                    borderWidth: 2,
                    borderDash: [5, 5],
                    pointRadius: 0,
                    tension: 0
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    position: 'top'
                }
            },
            scales: {
                y: {
                    beginAtZero: false,
                    min: 60,
                    max: 180
                }
            }
        }
    });
}

// 渲染区间分布图表
function renderZoneDistributionChart() {
    if (!appData.lotteryHistory) return;

    const chartEl = document.getElementById('zoneDistributionChart');
    if (!chartEl) return;

    // 计算区间分布 (01-11, 12-22, 23-33)
    const zones = {
        '01-11': 0,
        '12-22': 0,
        '23-33': 0
    };

    appData.lotteryHistory.data.forEach(draw => {
        draw.red_balls.forEach(ball => {
            const num = parseInt(ball);
            if (num >= 1 && num <= 11) zones['01-11']++;
            else if (num >= 12 && num <= 22) zones['12-22']++;
            else if (num >= 23 && num <= 33) zones['23-33']++;
        });
    });

    const labels = Object.keys(zones);
    const data = Object.values(zones);

    // 使用Chart.js渲染
    new Chart(chartEl, {
        type: 'bar',
        data: {
            labels: labels,
            datasets: [{
                label: '出现次数',
                data: data,
                backgroundColor: ['#fca5a5', '#93c5fd', '#d8b4fe'],
                borderRadius: 8
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    display: false
                }
            },
            scales: {
                y: {
                    beginAtZero: true,
                    ticks: {
                        stepSize: 10
                    }
                }
            }
        }
    });
}

// 渲染所有分析图表
function renderAllAnalysisCharts() {
    renderStatisticsCards();
    renderFrequencyChart();
    renderBlueFrequencyChart();
    renderOddEvenChart();
    renderSumTrendChart();
    renderZoneDistributionChart();
}

// 设置事件监听
function setupEventListeners() {
    // Tab切换 - 桌面端
    const navItems = document.querySelectorAll('.nav-item');
    navItems.forEach(item => {
        item.addEventListener('click', () => handleTabSwitch(item.dataset.tab, navItems));
    });

    // Tab切换 - 移动端
    const mobileNavItems = document.querySelectorAll('.mobile-nav-item');
    mobileNavItems.forEach(item => {
        item.addEventListener('click', () => handleTabSwitch(item.dataset.tab, mobileNavItems));
    });
}

// 处理Tab切换
function handleTabSwitch(tabName, navItems) {
    // 更新导航项状态
    navItems.forEach(item => {
        if (item.dataset.tab === tabName) {
            item.classList.add('active');
        } else {
            item.classList.remove('active');
        }
    });

    // 同步桌面端和移动端状态
    const allNavItems = document.querySelectorAll('.nav-item, .mobile-nav-item');
    allNavItems.forEach(item => {
        if (item.dataset.tab === tabName) {
            item.classList.add('active');
        } else {
            item.classList.remove('active');
        }
    });

    // 切换Tab内容
    const tabContents = document.querySelectorAll('.tab-content');
    tabContents.forEach(content => {
        if (content.dataset.tab === tabName) {
            content.classList.add('active');
        } else {
            content.classList.remove('active');
        }
    });

    // 如果切换到分析Tab，渲染所有图表
    if (tabName === 'analysis') {
        // 延迟渲染以确保canvas可见
        setTimeout(() => renderAllAnalysisCharts(), 100);
    }
}

// 隐藏加载屏幕
function hideLoadingScreen() {
    const loadingScreen = document.getElementById('loadingScreen');
    const mainApp = document.getElementById('mainApp');

    if (loadingScreen) {
        loadingScreen.style.display = 'none';
    }

    if (mainApp) {
        mainApp.style.display = 'block';
    }
}

// 计算距离目标日期的天数
function calculateDaysUntil(targetDateStr) {
    const today = new Date();
    today.setHours(0, 0, 0, 0);

    const targetDate = new Date(targetDateStr);
    targetDate.setHours(0, 0, 0, 0);

    const diffTime = targetDate - today;
    const diffDays = Math.ceil(diffTime / (1000 * 60 * 60 * 24));

    return diffDays;
}

// 页面加载完成后初始化
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initApp);
} else {
    initApp();
}
