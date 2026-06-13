export interface ThemeColors {
  // 背景
  background: string;
  surface: string;
  surfaceHover: string;
  muted: string;
  input: string;

  // 文字
  text: string;
  textSecondary: string;
  textTertiary: string;
  textInverse: string;

  // 边框
  border: string;
  borderSubtle: string;

  // 强调色
  accent: string;
  accentSubtle: string;

  // 风险色
  riskRed: string;
  riskRedBg: string;
  riskRedBorder: string;
  riskRedText: string;

  riskYellow: string;
  riskYellowBg: string;
  riskYellowBorder: string;
  riskYellowText: string;

  riskGreen: string;
  riskGreenBg: string;
  riskGreenBorder: string;
  riskGreenText: string;
}

export type ThemeMode = 'auto' | 'light' | 'dark';
