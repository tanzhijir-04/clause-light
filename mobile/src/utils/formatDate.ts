/**
 * 将 YYYY-MM-DD 格式的日期转为 "2026年6月" 格式的月份标题
 */
export const formatMonthHeader = (dateStr: string): string => {
  const [year, month] = dateStr.split('-');
  return `${year}年${parseInt(month, 10)}月`;
};

/**
 * 格式化日期为 "YYYY-MM-DD" 格式
 */
export const formatDate = (date: Date): string => {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, '0');
  const day = String(date.getDate()).padStart(2, '0');
  return `${year}-${month}-${day}`;
};

/**
 * 按月份分组合同列表
 */
export const groupByMonth = <T extends { createdAt: string }>(
  items: T[]
): { month: string; data: T[] }[] => {
  const groups: Record<string, T[]> = {};

  for (const item of items) {
    const monthKey = item.createdAt.substring(0, 7); // YYYY-MM
    if (!groups[monthKey]) {
      groups[monthKey] = [];
    }
    groups[monthKey].push(item);
  }

  return Object.entries(groups)
    .sort(([a], [b]) => b.localeCompare(a))
    .map(([month, data]) => ({
      month: formatMonthHeader(month + '-01'),
      data,
    }));
};
