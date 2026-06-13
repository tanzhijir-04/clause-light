import type { ThemeColors } from '../types/theme';

/**
 * 根据评分返回对应的风险颜色
 * >=70 绿色，>=50 黄色，<50 红色
 */
export const getScoreColor = (score: number, colors: ThemeColors): string => {
  if (score >= 70) return colors.riskGreen;
  if (score >= 50) return colors.riskYellow;
  return colors.riskRed;
};

/**
 * 根据评分返回风险等级
 */
export const getScoreLevel = (score: number): 'red' | 'yellow' | 'green' => {
  if (score >= 70) return 'green';
  if (score >= 50) return 'yellow';
  return 'red';
};
