import React from 'react';
import {
  Typography,
  DialogTitle,
  DialogContentText,
  TypographyProps,
  DialogTitleProps,
  styled,
} from '@mui/material';
import { flowVizTheme } from '../../theme/flowviz-theme';

// ============= Dialog Title Component =============

export const FlowDialogTitle = styled(DialogTitle)<DialogTitleProps>({
  color: flowVizTheme.colors.text.primary,
  fontSize: '1.125rem',
  fontWeight: 600,
  letterSpacing: '-0.02em',
  paddingBottom: `${flowVizTheme.spacing.md}px`,
  paddingTop: `${flowVizTheme.spacing.lg}px`,
  paddingLeft: `${flowVizTheme.spacing.lg}px`,
  paddingRight: `${flowVizTheme.spacing.lg}px`,
});

// ============= Dialog Content Text Component =============

export const FlowDialogContent = styled(DialogContentText)({
  color: flowVizTheme.colors.text.secondary,
  fontSize: '0.925rem',
  lineHeight: 1.6,
  letterSpacing: '0.01em',
});

// ============= Caption Text Variants =============

export const CaptionText = styled(Typography)<TypographyProps>({
  variant: 'caption',
  color: flowVizTheme.colors.text.tertiary,
  fontSize: '0.75rem',
  lineHeight: 1.4,
  letterSpacing: '0.01em',
});

export const CaptionTextSecondary = styled(Typography)<TypographyProps>({
  variant: 'caption',
  color: flowVizTheme.colors.text.secondary,
  fontSize: '0.75rem',
  lineHeight: 1.4,
  letterSpacing: '0.01em',
});

export const CaptionTextMuted = styled(Typography)<TypographyProps>({
  variant: 'caption',
  color: flowVizTheme.colors.text.disabled,
  fontSize: '0.75rem',
  lineHeight: 1.4,
  letterSpacing: '0.01em',
});

// Special uppercase caption variant used in nodes and headers
export const CaptionTextUppercase = styled(Typography)<TypographyProps>({
  variant: 'caption',
  color: flowVizTheme.colors.text.secondary,
  fontSize: '0.75rem',
  lineHeight: 1.4,
  letterSpacing: '0.05em',
  textTransform: 'uppercase',
  fontWeight: 500,
});

// ============= Small Text Variants =============

export const SmallText = styled(Typography)<TypographyProps>({
  fontSize: '0.8rem',
  color: flowVizTheme.colors.text.secondary,
  lineHeight: 1.4,
  letterSpacing: '0.01em',
});

export const SmallTextMuted = styled(Typography)<TypographyProps>({
  fontSize: '0.8rem',
  color: flowVizTheme.colors.text.tertiary,
  lineHeight: 1.4,
  letterSpacing: '0.01em',
});

// Special tiny text for node content
export const TinyText = styled(Typography)<TypographyProps>({
  fontSize: '0.7rem',
  color: flowVizTheme.colors.text.tertiary,
  lineHeight: 1.3,
  fontWeight: 500,
});

// ============= Status Text Components =============

interface StatusTextProps extends TypographyProps {
  status: 'success' | 'error' | 'warning' | 'info';
}

export const StatusText: React.FC<StatusTextProps> = ({ status, children, ...props }) => {
  const getStatusColor = () => {
    switch (status) {
      case 'success':
        return flowVizTheme.colors.status.success.text;
      case 'error':
        return flowVizTheme.colors.status.error.text;
      case 'warning':
        return flowVizTheme.colors.status.warning.text;
      case 'info':
        return flowVizTheme.colors.status.info.text;
      default:
        return flowVizTheme.colors.text.primary;
    }
  };

  return (
    <Typography
      {...props}
      sx={{
        color: getStatusColor(),
        fontSize: '0.875rem',
        fontWeight: 500,
        ...props.sx,
      }}
    >
      {children}
    </Typography>
  );
};

// ============= Section Headers =============

export const SectionHeader = styled(Typography)<TypographyProps>({
  fontSize: '1rem',
  fontWeight: 600,
  color: flowVizTheme.colors.text.primary,
  letterSpacing: '-0.01em',
  marginBottom: `${flowVizTheme.spacing.md}px`,
});

export const SubsectionHeader = styled(Typography)<TypographyProps>({
  fontSize: '0.875rem',
  fontWeight: 600,
  color: flowVizTheme.colors.text.primary,
  letterSpacing: '-0.01em',
  marginBottom: `${flowVizTheme.spacing.sm}px`,
  textTransform: 'uppercase',
});

// ============= Link Text Component =============

export const LinkText = styled(Typography)<TypographyProps>({
  color: flowVizTheme.colors.text.primary,
  textDecoration: 'underline',
  cursor: 'pointer',
  transition: flowVizTheme.motion.fast,
  
  '&:hover': {
    color: flowVizTheme.colors.text.primary,
    opacity: 0.8,
  },
  
  '&:active': {
    opacity: 0.6,
  },
});

// ============= Gradient Text Component =============

interface GradientTextProps extends TypographyProps {
  gradient?: 'primary' | 'secondary' | 'accent';
}

export const GradientText: React.FC<GradientTextProps> = ({ 
  gradient = 'primary', 
  children, 
  ...props 
}) => {
  const getGradient = () => {
    switch (gradient) {
      case 'primary':
        return `linear-gradient(135deg, ${flowVizTheme.colors.text.primary} 0%, ${flowVizTheme.colors.text.secondary} 100%)`;
      case 'secondary':
        return `linear-gradient(135deg, ${flowVizTheme.colors.text.secondary} 0%, ${flowVizTheme.colors.text.tertiary} 100%)`;
      case 'accent':
        return `linear-gradient(135deg, ${flowVizTheme.colors.surface.border.focus} 0%, ${flowVizTheme.colors.text.primary} 100%)`;
      default:
        return `linear-gradient(135deg, ${flowVizTheme.colors.text.primary} 0%, ${flowVizTheme.colors.text.secondary} 100%)`;
    }
  };

  return (
    <Typography
      {...props}
      sx={{
        background: getGradient(),
        WebkitBackgroundClip: 'text',
        WebkitTextFillColor: 'transparent',
        backgroundClip: 'text',
        ...props.sx,
      }}
    >
      {children}
    </Typography>
  );
};

// ============= Icon Text Wrapper =============

interface IconTextProps extends TypographyProps {
  icon: React.ReactNode;
  iconPosition?: 'start' | 'end';
  iconGap?: number;
}

export const IconText: React.FC<IconTextProps> = ({ 
  icon, 
  iconPosition = 'start', 
  iconGap = flowVizTheme.spacing.sm, 
  children, 
  ...props 
}) => {
  return (
    <Typography
      {...props}
      sx={{
        display: 'flex',
        alignItems: 'center',
        gap: `${iconGap}px`,
        flexDirection: iconPosition === 'end' ? 'row-reverse' : 'row',
        ...props.sx,
      }}
    >
      {icon}
      <span>{children}</span>
    </Typography>
  );
};

// ============= Icon Size Wrapper =============

interface FlowIconProps {
  children: React.ReactElement;
  size?: 'tiny' | 'small' | 'medium' | 'large';
  color?: 'primary' | 'secondary' | 'tertiary' | 'disabled';
}

export const FlowIcon: React.FC<FlowIconProps> = ({ 
  children, 
  size = 'small', 
  color = 'secondary' 
}) => {
  const getSize = () => {
    switch (size) {
      case 'tiny':
        return '16px';
      case 'small':
        return '18px';
      case 'medium':
        return '20px';
      case 'large':
        return '24px';
      default:
        return '18px';
    }
  };

  const getColor = () => {
    switch (color) {
      case 'primary':
        return flowVizTheme.colors.text.primary;
      case 'secondary':
        return flowVizTheme.colors.text.secondary;
      case 'tertiary':
        return flowVizTheme.colors.text.tertiary;
      case 'disabled':
        return flowVizTheme.colors.text.disabled;
      default:
        return flowVizTheme.colors.text.secondary;
    }
  };

  return React.cloneElement(children, {
    sx: {
      fontSize: getSize(),
      color: getColor(),
      ...children.props.sx,
    },
  });
};

// ============= Export all components =============

export default {
  FlowDialogTitle,
  FlowDialogContent,
  CaptionText,
  CaptionTextSecondary,
  CaptionTextMuted,
  CaptionTextUppercase,
  SmallText,
  SmallTextMuted,
  TinyText,
  StatusText,
  SectionHeader,
  SubsectionHeader,
  LinkText,
  GradientText,
  IconText,
  FlowIcon,
};