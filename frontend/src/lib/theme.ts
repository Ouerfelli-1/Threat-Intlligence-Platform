import { theme, ThemeConfig } from 'antd';

export const darkCyberTheme: ThemeConfig = {
  algorithm: theme.darkAlgorithm,
  token: {
    // Background layers
    colorBgContainer: '#0d1117',
    colorBgElevated: '#161b22',
    colorBgLayout: '#010409',
    colorBgSpotlight: '#1c2333',

    // Primary accent — electric blue
    colorPrimary: '#58a6ff',
    colorLink: '#58a6ff',

    // Borders
    colorBorder: '#21262d',
    colorBorderSecondary: '#30363d',

    // Text
    colorText: '#e6edf3',
    colorTextSecondary: '#8b949e',
    colorTextTertiary: '#484f58',

    // Semantic
    colorSuccess: '#3fb950',
    colorWarning: '#d29922',
    colorError: '#f85149',
    colorInfo: '#58a6ff',

    // Typography
    fontFamily: "'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif",
    fontSize: 14,
    borderRadius: 6,
  },
  components: {
    Table: {
      headerBg: '#161b22',
      rowHoverBg: '#1c2333',
      borderColor: '#21262d',
    },
    Menu: {
      darkItemBg: '#0d1117',
      darkItemSelectedBg: '#1c2333',
      darkItemHoverBg: '#161b22',
    },
    Card: {
      colorBgContainer: '#161b22',
    },
    Layout: {
      siderBg: '#0d1117',
      headerBg: '#0d1117',
      bodyBg: '#010409',
    },
    Input: {
      colorBgContainer: '#0d1117',
    },
    Select: {
      colorBgContainer: '#0d1117',
    },
    Modal: {
      contentBg: '#161b22',
      headerBg: '#161b22',
    },
    Drawer: {
      colorBgElevated: '#161b22',
    },
    Dropdown: {
      colorBgElevated: '#161b22',
    },
  },
};

// Severity colors
export const SEVERITY_COLORS: Record<string, { bg: string; text: string }> = {
  critical: { bg: '#f8514920', text: '#f85149' },
  high:     { bg: '#d2992220', text: '#d29922' },
  medium:   { bg: '#58a6ff20', text: '#58a6ff' },
  low:      { bg: '#3fb95020', text: '#3fb950' },
  info:     { bg: '#8b949e20', text: '#8b949e' },
};

// Analyst status colors
export const STATUS_COLORS: Record<string, string> = {
  unreviewed:   '#8b949e',
  relevant:     '#3fb950',
  not_relevant: '#f8514980',
  escalated:    '#d29922',
  reviewed:     '#58a6ff',
};
