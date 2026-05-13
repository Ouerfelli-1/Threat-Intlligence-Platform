import React from 'react';
import {
  TextField,
  TextFieldProps,
  InputAdornment,
  IconButton,
  styled,
  Box,
} from '@mui/material';
import SearchIcon from '@mui/icons-material/Search';
import ClearIcon from '@mui/icons-material/Clear';
import { flowVizTheme, createScrollbarStyle } from '../../theme/flowviz-theme';

// Base search input styling - fully monochrome using theme values
const searchInputStyles = {
  '& .MuiOutlinedInput-root': {
    color: flowVizTheme.colors.text.primary,
    backgroundColor: flowVizTheme.colors.background.glass,
    borderRadius: `${flowVizTheme.borderRadius.md}px`,
    transition: flowVizTheme.motion.normal,
    
    '&:hover': {
      backgroundColor: flowVizTheme.colors.background.glassLight,
    },
    
    '&.Mui-focused': {
      backgroundColor: flowVizTheme.colors.background.glassLight,
    },
    
    // Autofill handling for monochrome consistency
    '& input:-webkit-autofill, & input:-webkit-autofill:hover, & input:-webkit-autofill:focus': {
      WebkitTextFillColor: flowVizTheme.colors.text.primary,
      WebkitBoxShadow: `0 0 0px 1000px ${flowVizTheme.colors.background.glass} inset`,
      transition: 'background-color 5000s ease-in-out 0s',
      fontSize: 'inherit',
      caretColor: flowVizTheme.colors.text.primary,
    },
  },
  
  '& .MuiOutlinedInput-notchedOutline': {
    borderColor: flowVizTheme.colors.surface.border.default,
    borderWidth: 1,
    transition: flowVizTheme.motion.fast,
  },
  
  '& .MuiOutlinedInput-root:hover .MuiOutlinedInput-notchedOutline': {
    borderColor: flowVizTheme.colors.surface.border.emphasis,
  },
  
  // Monochrome focus - using theme value
  '& .MuiOutlinedInput-root.Mui-focused .MuiOutlinedInput-notchedOutline': {
    borderColor: flowVizTheme.colors.surface.border.focus,
    borderWidth: 1,
  },
  
  // Error state - using theme colors
  '& .MuiOutlinedInput-root.Mui-error .MuiOutlinedInput-notchedOutline': {
    borderColor: flowVizTheme.colors.status.error.border,
  },
  
  '& .MuiInputLabel-root': {
    color: flowVizTheme.colors.text.secondary,
    
    '&.Mui-focused': {
      color: flowVizTheme.colors.text.primary,
    },
    
    '&.Mui-error': {
      color: flowVizTheme.colors.status.error.text,
    },
  },
  
  '& input::placeholder, & textarea::placeholder': {
    color: flowVizTheme.colors.text.tertiary,
    opacity: 1,
    letterSpacing: '0.01em',
  },
  
  '& .MuiFormHelperText-root': {
    color: flowVizTheme.colors.text.tertiary,
    fontSize: '0.75rem',
    marginTop: `${flowVizTheme.spacing.xs}px`,
    
    '&.Mui-error': {
      color: flowVizTheme.colors.status.error.text,
    },
  },
};

// Compact variant styling for dialogs and smaller spaces
const compactSearchStyles = {
  ...searchInputStyles,
  '& .MuiOutlinedInput-root': {
    ...searchInputStyles['& .MuiOutlinedInput-root'],
    fontSize: '0.875rem',
    '& input': {
      padding: `${flowVizTheme.spacing.sm + 2}px ${flowVizTheme.spacing.sm + 6}px`,
    },
  },
};

// Standard search input
export const SearchInput = styled(TextField)<TextFieldProps>({
  ...searchInputStyles,
});

// Search input with integrated clear button
interface SearchInputWithClearProps extends Omit<TextFieldProps, 'InputProps'> {
  onClear?: () => void;
  showSearchIcon?: boolean;
}

export const SearchInputWithClear: React.FC<SearchInputWithClearProps> = ({
  value,
  onClear,
  showSearchIcon = true,
  ...props
}) => {
  const hasValue = Boolean(value);
  
  return (
    <SearchInput
      {...props}
      value={value}
      InputProps={{
        startAdornment: showSearchIcon ? (
          <InputAdornment position="start">
            <SearchIcon sx={{ color: flowVizTheme.colors.text.tertiary }} />
          </InputAdornment>
        ) : undefined,
        endAdornment: hasValue && onClear ? (
          <InputAdornment position="end">
            <IconButton
              size="small"
              onClick={onClear}
              sx={{
                color: flowVizTheme.colors.text.tertiary,
                '&:hover': {
                  color: flowVizTheme.colors.text.secondary,
                  backgroundColor: flowVizTheme.colors.surface.hover,
                },
              }}
            >
              <ClearIcon fontSize="small" />
            </IconButton>
          </InputAdornment>
        ) : undefined,
      }}
    />
  );
};

// Compact search input for dialogs
export const SearchInputCompact = styled(TextField)<TextFieldProps>({
  ...compactSearchStyles,
});

// URL input with larger height
export const SearchInputURL = styled(TextField)<TextFieldProps>({
  ...searchInputStyles,
  '& .MuiOutlinedInput-root': {
    ...searchInputStyles['& .MuiOutlinedInput-root'],
    height: 56,
  },
});

// Multiline search input for text content
export const SearchInputMultiline = styled(TextField)<TextFieldProps>({
  ...searchInputStyles,
  '& .MuiOutlinedInput-root': {
    ...searchInputStyles['& .MuiOutlinedInput-root'],
    '& textarea': {
      ...createScrollbarStyle(`${flowVizTheme.spacing.sm}px`),
    },
  },
});

// Search input with status indicator (for validation states)
interface SearchInputWithStatusProps extends Omit<TextFieldProps, 'error'> {
  status?: 'default' | 'warning' | 'error' | 'success';
  statusMessage?: string;
}

export const SearchInputWithStatus: React.FC<SearchInputWithStatusProps> = ({
  status = 'default',
  statusMessage,
  ...props
}) => {
  const getBorderColor = () => {
    switch (status) {
      case 'warning':
        return flowVizTheme.colors.status.warning.border;
      case 'error':
        return flowVizTheme.colors.status.error.border;
      case 'success':
        return flowVizTheme.colors.status.success.border;
      default:
        return flowVizTheme.colors.surface.border.default;
    }
  };
  
  const getTextColor = () => {
    switch (status) {
      case 'warning':
        return flowVizTheme.colors.status.warning.text;
      case 'error':
        return flowVizTheme.colors.status.error.text;
      case 'success':
        return flowVizTheme.colors.status.success.text;
      default:
        return flowVizTheme.colors.text.tertiary;
    }
  };
  
  return (
    <Box>
      <SearchInput
        {...props}
        error={status === 'error'}
        sx={{
          ...(props.sx as object || {}),
          '& .MuiOutlinedInput-notchedOutline': {
            borderColor: getBorderColor(),
          },
        }}
      />
      {statusMessage && (
        <Box
          sx={{
            mt: flowVizTheme.spacing.xs / 8,
            fontSize: '0.75rem',
            color: getTextColor(),
          }}
        >
          {statusMessage}
        </Box>
      )}
    </Box>
  );
};

// Export all components and utilities
export default {
  SearchInput,
  SearchInputWithClear,
  SearchInputCompact,
  SearchInputURL,
  SearchInputMultiline,
  SearchInputWithStatus,
};