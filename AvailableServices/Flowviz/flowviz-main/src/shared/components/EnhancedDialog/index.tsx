import React from 'react';
import {
  Dialog,
  DialogTitle,
  DialogContent, 
  DialogActions,
  Button,
  IconButton,
  Box,
  styled,
  DialogProps,
} from '@mui/material';
import CloseIcon from '@mui/icons-material/Close';
import { flowVizTheme, createGlassStyle, createInteractiveStyle } from '../../theme/flowviz-theme';

// Glass dialog variants
const createGlassDialogStyles = ({
  minHeight = '40vh',
  maxHeight = '80vh',
  minWidth,
  dialogMaxWidth,
}: {
  minHeight?: string;
  maxHeight?: string;
  minWidth?: string;
  dialogMaxWidth?: string;
} = {}) => ({
  '& .MuiPaper-root': {
    ...createGlassStyle(0.95),
    minHeight,
    maxHeight,
    ...(minWidth && { minWidth }),
    ...(dialogMaxWidth && { maxWidth: dialogMaxWidth }),
    margin: '16px',
    boxShadow: '0 20px 25px -5px rgba(0, 0, 0, 0.3), 0 10px 10px -5px rgba(0, 0, 0, 0.04)',
  },
});

const StyledDialog = styled(Dialog, {
  shouldForwardProp: (prop: string) => !['$minHeight', '$maxHeight', '$minWidth', '$dialogMaxWidth'].includes(prop),
})<{ 
  $minHeight?: string;
  $maxHeight?: string; 
  $minWidth?: string;
  $dialogMaxWidth?: string;
}>(({ $minHeight, $maxHeight, $minWidth, $dialogMaxWidth }: {
  $minHeight?: string;
  $maxHeight?: string; 
  $minWidth?: string;
  $dialogMaxWidth?: string;
}) => 
  createGlassDialogStyles({ 
    minHeight: $minHeight,
    maxHeight: $maxHeight,
    minWidth: $minWidth,
    dialogMaxWidth: $dialogMaxWidth
  })
);

const StyledDialogTitle = styled(DialogTitle)({
  color: flowVizTheme.colors.text.primary,
  fontSize: '1.125rem',
  fontWeight: 600,
  letterSpacing: '-0.02em',
  paddingBottom: flowVizTheme.spacing.md,
  paddingTop: flowVizTheme.spacing.lg,
  paddingLeft: flowVizTheme.spacing.lg,
  paddingRight: flowVizTheme.spacing.xl, // Extra space for close button
  // No border bottom - maintains clean design
  position: 'relative',
});

// DialogContent with proper spacing
const StyledDialogContent = styled(DialogContent)({
  padding: flowVizTheme.spacing.lg,
  paddingTop: `${flowVizTheme.spacing.lg}px !important`,
});

// DialogActions styling (no border separator)
const StyledDialogActions = styled(DialogActions)({
  padding: '16px 24px 20px',
  gap: flowVizTheme.spacing.sm,
  // No border top - maintains clean design
});

// Close button
const CloseButton = styled(IconButton)({
  position: 'absolute',
  right: flowVizTheme.spacing.md,
  top: '50%',
  transform: 'translateY(-50%)',
  color: flowVizTheme.colors.text.secondary,
  ...createInteractiveStyle(),
  padding: flowVizTheme.spacing.sm,
  '&:hover': {
    color: flowVizTheme.colors.text.primary,
    backgroundColor: flowVizTheme.colors.surface.hover,
  }
});

// Button variants
export const PrimaryButton = styled(Button)({
  background: 'rgba(255, 255, 255, 0.1)',
  color: 'rgba(255, 255, 255, 0.95)',
  textTransform: 'none',
  fontSize: '0.9rem',
  fontWeight: 500,
  letterSpacing: '0.01em',
  px: 2.5,
  py: 0.75,
  borderRadius: '8px',
  border: '1px solid rgba(255, 255, 255, 0.15)',
  transition: 'all 0.2s ease',
  '&:hover': {
    background: 'rgba(255, 255, 255, 0.15)',
    border: '1px solid rgba(255, 255, 255, 0.2)',
    transform: 'translateY(-1px)',
  },
  '&:active': {
    transform: 'translateY(0)',
  },
  '&:disabled': {
    background: flowVizTheme.colors.surface.rest,
    color: flowVizTheme.colors.text.disabled,
    borderColor: flowVizTheme.colors.surface.border.subtle,
  }
});

export const SecondaryButton = styled(Button)({
  color: 'rgba(255, 255, 255, 0.7)',
  textTransform: 'none',
  fontSize: '0.9rem',
  fontWeight: 500,
  letterSpacing: '0.01em',
  px: 2.5,
  py: 0.75,
  borderRadius: '8px',
  border: '1px solid transparent',
  transition: 'all 0.2s ease',
  '&:hover': {
    backgroundColor: 'rgba(255, 255, 255, 0.05)',
    color: 'rgba(255, 255, 255, 0.85)',
    border: '1px solid rgba(255, 255, 255, 0.1)',
  }
});

// Main Dialog Component
interface EnhancedDialogProps extends Omit<DialogProps, 'PaperProps'> {
  title?: string;
  onClose?: () => void;
  showCloseButton?: boolean;
  children?: React.ReactNode;
  // Glass dialog sizing variants (separate from MUI's maxWidth)
  minHeight?: string;
  maxHeight?: string;
  minWidth?: string;
  dialogMaxWidth?: string; // renamed to avoid conflict with MUI's maxWidth
  // Common dialog presets
  size?: 'small' | 'medium' | 'large' | 'fullscreen';
}

export const EnhancedDialog: React.FC<EnhancedDialogProps> = ({
  title,
  onClose,
  showCloseButton = true,
  children,
  minHeight,
  maxHeight,
  minWidth,
  dialogMaxWidth,
  size,
  ...props
}) => {
  // Handle size presets
  const getSizeProps = () => {
    switch (size) {
      case 'small':
        return { minWidth: '420px', dialogMaxWidth: '480px', minHeight: '30vh', maxHeight: '60vh' };
      case 'medium':
        return { minHeight: '40vh', maxHeight: '70vh' };
      case 'large':
        return { minHeight: '60vh', maxHeight: '80vh' };
      case 'fullscreen':
        return { minHeight: '90vh', maxHeight: '90vh' };
      default:
        return { minHeight, maxHeight, minWidth, dialogMaxWidth };
    }
  };
  
  const sizeProps = getSizeProps();
  
  return (
    <StyledDialog
      {...props}
      $minHeight={sizeProps.minHeight}
      $maxHeight={sizeProps.maxHeight}
      $minWidth={sizeProps.minWidth}
      $dialogMaxWidth={sizeProps.dialogMaxWidth}
      onClose={onClose}
      disableRestoreFocus
      disableEnforceFocus
    >
      {title && (
        <StyledDialogTitle>
          {title}
          {showCloseButton && onClose && (
            <CloseButton onClick={onClose} size="small">
              <CloseIcon fontSize="small" />
            </CloseButton>
          )}
        </StyledDialogTitle>
      )}
      {children}
    </StyledDialog>
  );
};

// Dialog Content and Actions exports
export { StyledDialogContent as EnhancedDialogContent };
export { StyledDialogActions as EnhancedDialogActions };