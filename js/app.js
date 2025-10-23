/**
 * 主应用逻辑
 * 负责页面初始化、事件处理和数据展示协调
 */

class LotteryApp {
    constructor() {
        this.lotteryData = null;
        this.predictionData = null;
        this.predictionsHistoryData = null;
        this.selectedModel = null;
        this.currentTheme = 'light';

        // DOM 元素引用
        this.elements = {
            loadingScreen: document.getElementById('loadingScreen'),
            mainApp: document.getElementById('mainApp'),
            btnRefresh: document.getElementById('btnRefresh'),
            btnTheme: document.getElementById('btnTheme'),
            tabTriggers: document.querySelectorAll('.tab-trigger'),
            tabContents: document.querySelectorAll('.tab-content'),
            nextDrawCard: document.getElementById('nextDrawCard'),
            nextPeriod: document.getElementById('nextPeriod'),
            nextDate: document.getElementById('nextDate'),
            predictionAvailability: document.getElementById('predictionAvailability'),
            latestPeriod: document.getElementById('latestPeriod'),
            latestDate: document.getElementById('latestDate'),
            latestBalls: document.getElementById('latestBalls'),
            predictionStatusCard: document.getElementById('predictionStatusCard'),
            predictionStatus: document.getElementById('predictionStatus'),
            statusIcon: document.getElementById('statusIcon'),
            statusText: document.getElementById('statusText'),
            statusDescription: document.getElementById('statusDescription'),
            modelSelector: document.getElementById('modelSelector'),
            currentModelName: document.getElementById('currentModelName'),
            targetPeriod: document.getElementById('targetPeriod'),
            predictionsGrid: document.getElementById('predictionsGrid'),
            predictionsHistoryContainer: document.getElementById('predictionsHistoryContainer'),
            historyLastUpdate: document.getElementById('historyLastUpdate'),
            historyList: document.getElementById('historyList')
        };

        this.init();
    }

    /**
     * 初始化应用
     */
    async init() {
        console.log('初始化双色球数据展示应用...');

        // 绑定事件
        this.bindEvents();

        // 加载数据
        await this.loadAllData();

        // 隐藏加载屏幕，显示主应用
        this.hideLoading();
    }

    /**
     * 绑定事件处理器
     */
    bindEvents() {
        // 刷新按钮
        this.elements.btnRefresh.addEventListener('click', () => {
            this.showLoading();
            this.loadAllData();
        });

        // 主题切换按钮
        this.elements.btnTheme.addEventListener('click', () => this.toggleTheme());

        // Tab 切换
        this.elements.tabTriggers.forEach(trigger => {
            trigger.addEventListener('click', (e) => {
                const tabName = e.target.dataset.tab;
                this.switchTab(tabName);
            });
        });
    }

    /**
     * 切换主题
     */
    toggleTheme() {
        this.currentTheme = this.currentTheme === 'light' ? 'dark' : 'light';
        document.body.className = `${this.currentTheme}-theme`;

        // 保存到本地存储
        localStorage.setItem('theme', this.currentTheme);
    }

    /**
     * 加载主题设置
     */
    loadTheme() {
        const savedTheme = localStorage.getItem('theme');
        if (savedTheme) {
            this.currentTheme = savedTheme;
            document.body.className = `${this.currentTheme}-theme`;
        }
    }

    /**
     * 切换 Tab
     */
    switchTab(tabName) {
        // 更新 tab triggers
        this.elements.tabTriggers.forEach(trigger => {
            if (trigger.dataset.tab === tabName) {
                trigger.classList.add('active');
            } else {
                trigger.classList.remove('active');
            }
        });

        // 更新 tab contents
        this.elements.tabContents.forEach(content => {
            if (content.dataset.tab === tabName) {
                content.classList.add('active');
            } else {
                content.classList.remove('active');
            }
        });
    }

    /**
     * 显示加载屏幕
     */
    showLoading() {
        this.elements.loadingScreen.style.display = 'flex';
        this.elements.mainApp.style.display = 'none';
    }

    /**
     * 隐藏加载屏幕
     */
    hideLoading() {
        this.elements.loadingScreen.style.display = 'none';
        this.elements.mainApp.style.display = 'block';
    }

    /**
     * 加载所有数据
     */
    async loadAllData() {
        try {
            const data = await DataLoader.loadAllData();

            this.lotteryData = data.lottery;
            this.predictionData = data.predictions;
            this.predictionsHistoryData = data.predictionsHistory;

            // 渲染最新开奖结果
            this.renderLatestResult();

            // 渲染下一期开奖信息
            this.renderNextDrawInfo();

            // 渲染预测状态
            this.renderPredictionStatus();

            // 渲染模型选择器
            this.renderModelSelector();

            // 渲染历史预测对比
            this.renderPredictionsHistory();

            // 渲染历史记录
            this.renderHistory();

            console.log('数据加载完成');
        } catch (error) {
            console.error('加载数据失败:', error);
            alert('加载数据失败，请刷新页面重试');
        }
    }

    /**
     * 渲染最新开奖结果
     */
    renderLatestResult() {
        if (!this.lotteryData || !this.lotteryData.data || this.lotteryData.data.length === 0) {
            return;
        }

        const latest = this.lotteryData.data[0];

        this.elements.latestPeriod.textContent = `第 ${latest.period} 期`;
        this.elements.latestDate.textContent = latest.date;

        // 清空并渲染号码球
        this.elements.latestBalls.innerHTML = '';
        this.elements.latestBalls.appendChild(
            Components.createBallsContainer(latest.red_balls, latest.blue_ball)
        );
    }

    /**
     * 渲染下一期开奖信息
     */
    renderNextDrawInfo() {
        if (!this.lotteryData || !this.lotteryData.next_draw) {
            this.elements.nextDrawCard.style.display = 'none';
            return;
        }

        const nextDraw = this.lotteryData.next_draw;

        // 显示卡片
        this.elements.nextDrawCard.style.display = 'block';

        // 设置期号和日期
        this.elements.nextPeriod.textContent = `第 ${nextDraw.next_period} 期`;
        this.elements.nextDate.textContent = `${nextDraw.next_date_display} ${nextDraw.weekday} ${nextDraw.draw_time}`;

        // 检查是否有对应的AI预测
        const hasPrediction = this.predictionData &&
                             this.predictionData.target_period === nextDraw.next_period;

        // 更新预测可用性状态
        const availabilityEl = this.elements.predictionAvailability;
        availabilityEl.classList.remove('has-prediction', 'no-prediction');

        if (hasPrediction) {
            availabilityEl.classList.add('has-prediction');
            availabilityEl.querySelector('.availability-icon').textContent = '✓';
            availabilityEl.querySelector('.availability-text').textContent = '已有AI预测';
        } else {
            availabilityEl.classList.add('no-prediction');
            availabilityEl.querySelector('.availability-icon').textContent = '⚠';
            availabilityEl.querySelector('.availability-text').textContent = '暂无AI预测';
        }
    }

    /**
     * 渲染预测状态
     */
    renderPredictionStatus() {
        if (!this.lotteryData || !this.lotteryData.data || this.lotteryData.data.length === 0) {
            this.elements.predictionStatusCard.style.display = 'none';
            return;
        }

        if (!this.predictionData || !this.predictionData.target_period) {
            this.elements.predictionStatusCard.style.display = 'none';
            return;
        }

        this.elements.predictionStatusCard.style.display = 'block';

        const latestPeriod = parseInt(this.lotteryData.data[0].period);
        const targetPeriod = parseInt(this.predictionData.target_period);

        // 清除之前的状态类
        this.elements.predictionStatus.classList.remove('status-未开奖', 'status-已开奖');

        if (targetPeriod > latestPeriod) {
            // 预测的是未来期号 - 等待开奖
            this.elements.predictionStatus.classList.add('status-未开奖');
            this.elements.statusIcon.textContent = '🔮';
            this.elements.statusText.textContent = '等待开奖';
            this.elements.statusDescription.textContent =
                `预测期号 ${targetPeriod} 尚未开奖，当前最新期号为 ${latestPeriod}。请等待开奖后查看预测结果。`;
        } else {
            // 预测期号已开奖
            this.elements.predictionStatus.classList.add('status-已开奖');
            this.elements.statusIcon.textContent = '✅';
            this.elements.statusText.textContent = '已开奖';
            this.elements.statusDescription.textContent =
                `预测期号 ${targetPeriod} 已开奖，可以查看预测准确度。下方显示各策略的预测结果与实际开奖号码的对比。`;
        }
    }

    /**
     * 渲染模型选择器
     */
    renderModelSelector() {
        if (!this.predictionData || !this.predictionData.models || this.predictionData.models.length === 0) {
            this.elements.modelSelector.innerHTML = '<p>暂无预测数据</p>';
            return;
        }

        this.elements.modelSelector.innerHTML = '';

        this.predictionData.models.forEach((model, index) => {
            const btn = document.createElement('button');
            btn.className = 'model-btn';
            btn.textContent = model.model_name;

            // 默认选中第一个模型
            if (index === 0) {
                btn.classList.add('active');
                this.selectedModel = model.model_id;
            }

            btn.addEventListener('click', () => {
                this.selectModel(model.model_id);
            });

            this.elements.modelSelector.appendChild(btn);
        });

        // 渲染第一个模型的预测
        this.renderPredictions();
    }

    /**
     * 选择模型
     */
    selectModel(modelId) {
        this.selectedModel = modelId;

        // 更新按钮状态
        const buttons = this.elements.modelSelector.querySelectorAll('.model-btn');
        buttons.forEach(btn => {
            btn.classList.remove('active');
        });

        const selectedBtn = Array.from(buttons).find(btn => {
            const model = this.predictionData.models.find(m => m.model_name === btn.textContent);
            return model && model.model_id === modelId;
        });

        if (selectedBtn) {
            selectedBtn.classList.add('active');
        }

        // 重新渲染预测
        this.renderPredictions();
    }

    /**
     * 渲染预测
     */
    renderPredictions() {
        const model = this.predictionData.models.find(m => m.model_id === this.selectedModel);

        if (!model) {
            this.elements.predictionsGrid.innerHTML = '<p>未找到该模型的预测数据</p>';
            return;
        }

        // 更新标题和期号
        this.elements.currentModelName.textContent = `${model.model_name} 的预测`;
        this.elements.targetPeriod.textContent = `预测期号: ${this.predictionData.target_period}`;

        // 获取最新开奖结果用于对比
        const latestResult = this.lotteryData.data && this.lotteryData.data.length > 0
            ? this.lotteryData.data[0]
            : null;

        // 清空并渲染预测卡片
        this.elements.predictionsGrid.innerHTML = '';

        model.predictions.forEach(prediction => {
            const card = Components.createPredictionCard(prediction, latestResult);
            this.elements.predictionsGrid.appendChild(card);
        });
    }

    /**
     * 渲染历史记录
     */
    renderHistory() {
        if (!this.lotteryData || !this.lotteryData.data || this.lotteryData.data.length === 0) {
            this.elements.historyList.innerHTML = '<p>暂无历史数据</p>';
            return;
        }

        // 更新最后更新时间
        if (this.lotteryData.last_updated) {
            this.elements.historyLastUpdate.textContent =
                `最后更新: ${Components.formatDateTime(this.lotteryData.last_updated)}`;
        }

        // 清空并渲染历史记录
        this.elements.historyList.innerHTML = '';

        this.lotteryData.data.forEach(record => {
            const item = Components.createHistoryItem(record);
            this.elements.historyList.appendChild(item);
        });
    }

    /**
     * 渲染历史预测对比
     */
    renderPredictionsHistory() {
        if (!this.predictionsHistoryData ||
            !this.predictionsHistoryData.predictions_history ||
            this.predictionsHistoryData.predictions_history.length === 0) {
            this.elements.predictionsHistoryContainer.innerHTML = '<p>暂无历史预测对比数据</p>';
            return;
        }

        // 清空容器
        this.elements.predictionsHistoryContainer.innerHTML = '';

        // 渲染每个历史预测记录
        this.predictionsHistoryData.predictions_history.forEach(historyRecord => {
            const card = Components.createHistoricalPredictionCard(historyRecord);
            this.elements.predictionsHistoryContainer.appendChild(card);
        });
    }
}

// 页面加载完成后初始化应用
document.addEventListener('DOMContentLoaded', () => {
    window.app = new LotteryApp();
});
