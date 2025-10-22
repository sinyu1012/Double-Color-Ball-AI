/**
 * 数据加载模块
 * 负责从 JSON 文件加载历史开奖数据和 AI 预测数据
 */

const DataLoader = {
    /**
     * 加载历史开奖数据
     * @returns {Promise<Object>} 历史数据对象
     */
    async loadLotteryHistory() {
        try {
            const response = await fetch('./data/lottery_history.json');
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            const data = await response.json();
            console.log('历史开奖数据加载成功', data);
            return data;
        } catch (error) {
            console.error('加载历史开奖数据失败:', error);
            throw error;
        }
    },

    /**
     * 加载 AI 预测数据
     * @returns {Promise<Object>} AI 预测数据对象
     */
    async loadPredictions() {
        try {
            const response = await fetch('./data/ai_predictions.json');
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            const data = await response.json();
            console.log('AI 预测数据加载成功', data);
            return data;
        } catch (error) {
            console.error('加载 AI 预测数据失败:', error);
            throw error;
        }
    },

    /**
     * 加载历史预测对比数据
     * @returns {Promise<Object>} 历史预测对比数据对象
     */
    async loadPredictionsHistory() {
        try {
            const response = await fetch('./data/predictions_history.json');
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            const data = await response.json();
            console.log('历史预测对比数据加载成功', data);
            return data;
        } catch (error) {
            console.error('加载历史预测对比数据失败:', error);
            throw error;
        }
    },

    /**
     * 加载所有数据
     * @returns {Promise<Object>} 包含历史数据和预测数据的对象
     */
    async loadAllData() {
        try {
            const [lotteryData, predictionData, predictionsHistoryData] = await Promise.all([
                this.loadLotteryHistory(),
                this.loadPredictions(),
                this.loadPredictionsHistory()
            ]);

            return {
                lottery: lotteryData,
                predictions: predictionData,
                predictionsHistory: predictionsHistoryData
            };
        } catch (error) {
            console.error('加载数据失败:', error);
            throw error;
        }
    }
};

// 导出到全局作用域
window.DataLoader = DataLoader;
