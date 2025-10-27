// 模拟完整的前端逻辑
console.log('=== 模拟前端预测对比逻辑 ===\n');

// 模拟数据
const lotteryData = {
    data: [
        { period: "25123", red_balls: ["07", "09", "23", "24", "25", "26"], blue_ball: "10" },
        { period: "25122", red_balls: ["16", "18", "19", "20", "25", "31"], blue_ball: "13" }
    ]
};

const predictionData = {
    target_period: "25124",
    models: [{
        model_name: "GPT-5",
        predictions: [{
            red_balls: ["09", "16", "24", "25", "26", "31"],
            blue_ball: "08"
        }]
    }]
};

// renderPredictions() 方法的逻辑
console.log('1. 获取期号信息:');
const targetPeriod = predictionData.target_period;
const latestPeriod = lotteryData.data[0].period;
console.log(`   预测期号: ${targetPeriod}`);
console.log(`   最新期号: ${latestPeriod}`);

console.log('\n2. 判断是否需要对比:');
console.log(`   parseInt("${targetPeriod}") = ${parseInt(targetPeriod)}`);
console.log(`   parseInt("${latestPeriod}") = ${parseInt(latestPeriod)}`);
console.log(`   ${parseInt(targetPeriod)} <= ${parseInt(latestPeriod)} ? ${parseInt(targetPeriod) <= parseInt(latestPeriod)}`);

console.log('\n3. 执行查找逻辑:');
let actualResult = null;
if (lotteryData.data && lotteryData.data.length > 0) {
    if (parseInt(targetPeriod) <= parseInt(latestPeriod)) {
        actualResult = lotteryData.data.find(item => item.period === targetPeriod);
        console.log(`   ✓ 已开奖，查找期号 ${targetPeriod} 的结果`);
        console.log(`   查找结果: ${actualResult ? JSON.stringify(actualResult) : 'null'}`);
    } else {
        console.log(`   ✓ 未开奖，不查找 (actualResult = null)`);
    }
}

console.log('\n4. createPredictionCard 接收参数:');
const prediction = predictionData.models[0].predictions[0];
console.log(`   prediction: ${JSON.stringify(prediction)}`);
console.log(`   actualResult: ${actualResult ? JSON.stringify(actualResult) : 'null'}`);

console.log('\n5. compareNumbers 对比逻辑:');
if (!actualResult) {
    console.log('   ✓ actualResult 为 null，返回 null (不对比)');
} else {
    console.log('   ✓ actualResult 不为 null，执行对比');
    const redHits = prediction.red_balls.filter(ball => actualResult.red_balls.includes(ball));
    console.log(`   红球命中: ${JSON.stringify(redHits)}`);
}

console.log('\n=== 最终结果 ===');
console.log(actualResult ? '❌ 会显示命中高亮' : '✅ 不会显示命中高亮');
console.log('');
