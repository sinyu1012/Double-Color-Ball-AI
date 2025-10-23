#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
双色球历史开奖数据获取脚本

功能：
1. 从 500 彩票网爬取双色球历史开奖数据
2. 支持指定爬取期数范围
3. 自动保存为 JSON 格式，方便后续使用
4. 包含错误处理和重试机制

使用方法：
    python3 fetch_lottery_history.py
    
输出：
    lottery_data.json - 包含所有开奖数据的 JSON 文件
"""

import requests
from bs4 import BeautifulSoup
import json
import time
import sys
import os
from datetime import datetime, timedelta


class LotteryDataFetcher:
    """双色球数据获取器"""
    
    def __init__(self):
        self.base_url = "https://datachart.500.com/ssq/history/history.shtml"
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
        }
        self.session = requests.Session()
        self.session.headers.update(self.headers)
    
    def fetch_page(self, url, retry=3):
        """
        获取网页内容
        
        Args:
            url: 目标 URL
            retry: 重试次数
            
        Returns:
            BeautifulSoup 对象或 None
        """
        for attempt in range(retry):
            try:
                print(f"正在获取数据... (尝试 {attempt + 1}/{retry})")
                response = self.session.get(url, timeout=10)
                response.encoding = 'gb2312'  # 500彩票网使用 gb2312 编码
                
                if response.status_code == 200:
                    return BeautifulSoup(response.text, 'html.parser')
                else:
                    print(f"HTTP 状态码: {response.status_code}")
                    
            except requests.exceptions.RequestException as e:
                print(f"请求失败: {e}")
                if attempt < retry - 1:
                    time.sleep(2)
                    
        return None
    
    def parse_lottery_data(self, soup):
        """
        解析开奖数据
        
        Args:
            soup: BeautifulSoup 对象
            
        Returns:
            开奖数据列表
        """
        data_list = []
        
        try:
            # 查找数据表格 - 500彩票网的表格结构
            table = soup.find('tbody')
            if not table:
                # 尝试查找 table 标签
                table = soup.find('table')
                if not table:
                    print("未找到数据表格")
                    return data_list
            
            # 获取所有数据行
            rows = table.find_all('tr')
            if not rows:
                print("表格中没有数据行")
                return data_list
            
            for row in rows:
                cols = row.find_all('td')
                
                # 确保列数足够
                if len(cols) < 9:
                    continue
                
                try:
                    # 提取期号
                    period = cols[0].text.strip()
                    
                    # 提取红球（6个）
                    red_balls = [cols[i].text.strip() for i in range(1, 7)]
                    
                    # 提取蓝球
                    blue_ball = cols[7].text.strip()
                    
                    # 提取开奖日期（如果有）
                    date = cols[-1].text.strip() if len(cols) > 8 else ""
                    
                    # 构建数据对象
                    lottery_item = {
                        "period": period,
                        "red_balls": red_balls,
                        "blue_ball": blue_ball,
                        "date": date
                    }
                    
                    data_list.append(lottery_item)
                    
                except Exception as e:
                    print(f"解析行数据时出错: {e}")
                    continue
            
            print(f"成功解析 {len(data_list)} 期数据")
            
        except Exception as e:
            print(f"解析数据时发生错误: {e}")
        
        return data_list
    
    def merge_with_existing_data(self, new_data, existing_file):
        """
        合并新数据和现有数据，去重并保留所有历史记录

        Args:
            new_data: 新获取的数据列表
            existing_file: 现有数据文件路径

        Returns:
            合并后的数据列表
        """
        existing_data = []

        # 如果文件存在，加载现有数据
        if os.path.exists(existing_file):
            try:
                with open(existing_file, 'r', encoding='utf-8') as f:
                    existing_data = json.load(f)
                print(f"已加载现有数据: {len(existing_data)} 期")
            except Exception as e:
                print(f"加载现有数据时出错: {e}")

        # 使用期号作为键来去重
        data_dict = {}

        # 先加载现有数据
        for item in existing_data:
            data_dict[item['period']] = item

        # 合并新数据（新数据会覆盖同期号的旧数据）
        new_count = 0
        for item in new_data:
            if item['period'] not in data_dict:
                new_count += 1
            data_dict[item['period']] = item

        # 转换回列表并按期号降序排序
        merged_data = list(data_dict.values())
        merged_data.sort(key=lambda x: x['period'], reverse=True)

        print(f"合并完成: 新增 {new_count} 期, 总计 {len(merged_data)} 期")

        return merged_data

    def backup_existing_file(self, filename):
        """
        备份现有文件

        Args:
            filename: 要备份的文件名
        """
        if os.path.exists(filename):
            # 生成带时间戳的备份文件名
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_name = filename.replace('.json', f'_backup_{timestamp}.json')

            try:
                # 复制文件
                import shutil
                shutil.copy2(filename, backup_name)
                print(f"已创建备份文件: {backup_name}")
                return backup_name
            except Exception as e:
                print(f"创建备份时出错: {e}")
                return None
        return None

    def predict_next_draw(self, latest_period, latest_date):
        """
        预测下一期开奖信息

        双色球开奖规律：每周二、四、日开奖（晚上21:15）

        Args:
            latest_period: 最新期号
            latest_date: 最新开奖日期字符串 (YYYY-MM-DD)

        Returns:
            包含下一期期号和日期的字典
        """
        try:
            # 解析最新期号和日期
            period_num = int(latest_period)
            last_draw_date = datetime.strptime(latest_date, '%Y-%m-%d')

            # 双色球开奖日：周二(1), 周四(3), 周日(6)
            draw_weekdays = [1, 3, 6]

            # 从最新开奖日期的下一天开始查找
            next_date = last_draw_date + timedelta(days=1)

            # 找到下一个开奖日
            while next_date.weekday() not in draw_weekdays:
                next_date += timedelta(days=1)

            # 计算下一期期号
            next_period = str(period_num + 1).zfill(len(latest_period))

            # 格式化日期
            next_date_str = next_date.strftime('%Y-%m-%d')
            next_date_display = next_date.strftime('%Y年%m月%d日')

            # 计算星期
            weekday_names = ['周一', '周二', '周三', '周四', '周五', '周六', '周日']
            weekday = weekday_names[next_date.weekday()]

            return {
                'next_period': next_period,
                'next_date': next_date_str,
                'next_date_display': next_date_display,
                'weekday': weekday,
                'draw_time': '21:15'
            }

        except Exception as e:
            print(f"预测下一期信息时出错: {e}")
            return None

    def format_for_web(self, data):
        """
        格式化数据为网页使用的格式

        Args:
            data: 原始数据列表

        Returns:
            格式化后的数据字典
        """
        formatted = {
            "last_updated": datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ"),
            "data": data
        }

        # 添加下一期预测信息
        if data and len(data) > 0:
            latest = data[0]
            next_draw_info = self.predict_next_draw(latest['period'], latest['date'])
            if next_draw_info:
                formatted['next_draw'] = next_draw_info

        return formatted

    def save_to_json(self, data, filename="lottery_data.json", preserve_history=True):
        """
        保存数据到 JSON 文件

        Args:
            data: 要保存的数据
            filename: 文件名
            preserve_history: 是否保留历史数据（合并模式）
        """
        try:
            if preserve_history:
                # 备份现有文件
                self.backup_existing_file(filename)

                # 合并数据
                merged_data = self.merge_with_existing_data(data, filename)

                # 保存合并后的数据
                with open(filename, 'w', encoding='utf-8') as f:
                    json.dump(merged_data, f, ensure_ascii=False, indent=2)
                print(f"\n数据已成功保存到 {filename}")
                print(f"共保存 {len(merged_data)} 期数据")

                # 同时更新到 ../data/lottery_history.json
                try:
                    web_data_path = os.path.join(os.path.dirname(filename), '..', 'data', 'lottery_history.json')
                    formatted_data = self.format_for_web(merged_data)

                    with open(web_data_path, 'w', encoding='utf-8') as f:
                        json.dump(formatted_data, f, ensure_ascii=False, indent=2)
                    print(f"✓ 已同步到网页数据文件: {web_data_path}")
                except Exception as e:
                    print(f"⚠️  同步到网页数据失败: {e}")

            else:
                # 直接保存新数据
                with open(filename, 'w', encoding='utf-8') as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
                print(f"\n数据已成功保存到 {filename}")
                print(f"共保存 {len(data)} 期数据")
        except Exception as e:
            print(f"保存文件时出错: {e}")
    
    def fetch_and_save(self, output_file="lottery_data.json", preserve_history=True):
        """
        获取并保存数据的主函数

        Args:
            output_file: 输出文件名
            preserve_history: 是否保留并合并历史数据
        """
        print("=" * 50)
        print("双色球历史开奖数据获取工具")
        print("=" * 50)

        # 获取网页
        soup = self.fetch_page(self.base_url)

        if not soup:
            print("获取网页失败，请检查网络连接或稍后重试")
            return False

        # 解析数据
        lottery_data = self.parse_lottery_data(soup)

        if not lottery_data:
            print("未能解析到任何数据")
            return False

        # 显示最新几期数据作为预览
        print("\n最新 5 期数据预览：")
        print("-" * 50)
        for item in lottery_data[:5]:
            red_str = " ".join(item['red_balls'])
            print(f"期号: {item['period']} | 红球: {red_str} | 蓝球: {item['blue_ball']} | 日期: {item['date']}")

        # 保存数据
        self.save_to_json(lottery_data, output_file, preserve_history)

        return True


def main():
    """主函数"""
    fetcher = LotteryDataFetcher()
    
    # 可以自定义输出文件名
    output_file = "lottery_data.json"
    
    if len(sys.argv) > 1:
        output_file = sys.argv[1]
    
    success = fetcher.fetch_and_save(output_file)
    
    if success:
        print("\n✓ 数据获取完成！")
        print(f"✓ 文件位置: {output_file}")
    else:
        print("\n✗ 数据获取失败")
        sys.exit(1)


if __name__ == "__main__":
    main()

