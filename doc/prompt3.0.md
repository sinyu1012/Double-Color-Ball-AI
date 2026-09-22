# 双色球候选选择 v3.0

为 {target_period} 期（{target_date}）从下方已校验候选中，每个策略选择一组，共 5 组。

候选由程序根据真实开奖计算统计、生成号码并校验。排名、并列处理、蓝球选择与扩池均由程序确定；必要调整记录在 adjustments。你只选择 candidate_id，不得自行改号码、放宽规则、重新计算统计或编造描述。

选择时结合候选中的说明与跨组差异：各组红球组合不得完全相同。候选次序代表程序按策略排序后的枚举次序，并非中奖概率排序。

{candidate_plan}

仅返回一个 JSON 对象，包含 selections 数组；必须恰好覆盖整数 group_id 1、2、3、4、5，各出现一次，candidate_id 必须属于对应组。示例：
{{"selections":[{{"group_id":1,"candidate_id":"1-01"}},{{"group_id":2,"candidate_id":"2-01"}},{{"group_id":3,"candidate_id":"3-01"}},{{"group_id":4,"candidate_id":"4-01"}},{{"group_id":5,"candidate_id":"5-01"}}]}}

示例只说明结构，请实际检查所选组合之间没有重复。不要输出 Markdown、解释或其他字段。期号、日期、模型名称、号码和描述会由程序填入正式结果。
