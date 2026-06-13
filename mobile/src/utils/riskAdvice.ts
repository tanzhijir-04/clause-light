/**
 * 根据评分返回风险建议文字
 */
export const getRiskAdvice = (score: number): string => {
  if (score >= 80) return '风险较低，可以签署';
  if (score >= 70) return '风险可控，建议关注细节';
  if (score >= 50) return '存在一定风险，建议协商修改后再签';
  if (score >= 30) return '风险较高，强烈建议协商修改';
  return '风险极高，建议不要签署';
};

/**
 * 根据推荐类型返回建议文字
 */
export const getRecommendationText = (recommendation: string): string => {
  switch (recommendation) {
    case 'sign':
      return '建议签署';
    case 'negotiate_first':
      return '建议协商后再签';
    case 'reject':
      return '建议不要签署';
    default:
      return '';
  }
};

/**
 * 获取风险等级中文名
 */
export const getRiskLevelName = (level: 'red' | 'yellow' | 'green'): string => {
  switch (level) {
    case 'red':
      return '高风险';
    case 'yellow':
      return '中风险';
    case 'green':
      return '低风险';
  }
};
