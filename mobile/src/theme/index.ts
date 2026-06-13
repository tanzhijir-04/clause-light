export { lightColors, darkColors } from './colors';
export { spacing, borderRadius } from './spacing';
export { fontSize, fontWeight } from './typography';
export type { ThemeColors } from '../types/theme';

import { lightColors, darkColors } from './colors';
import type { ThemeColors } from '../types/theme';

export const getThemeColors = (mode: 'light' | 'dark'): ThemeColors => {
  return mode === 'dark' ? darkColors : lightColors;
};
