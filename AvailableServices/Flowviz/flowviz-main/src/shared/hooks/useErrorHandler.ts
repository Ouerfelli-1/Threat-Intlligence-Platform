import { useState, useCallback } from 'react';
import { ClaudeServiceError, NetworkError, APIError, ValidationError } from '../services/claude';

export interface ErrorState {
  error: Error | null;
  isErrorVisible: boolean;
  errorDetails: {
    title: string;
    message: string;
    severity: 'error' | 'warning' | 'info' | 'success';
    suggestion?: string;
    canRetry: boolean;
  } | null;
}

export const useErrorHandler = () => {
  const [errorState, setErrorState] = useState<ErrorState>({
    error: null,
    isErrorVisible: false,
    errorDetails: null
  });

  const getErrorDetails = useCallback((error: Error) => {
    if (error instanceof NetworkError) {
      return {
        title: 'Network Connection Failed',
        message: error.message,
        severity: 'error' as const,
        suggestion: 'Please check your internet connection and try again.',
        canRetry: true
      };
    }
    
    if (error instanceof APIError) {
      if (error.statusCode === 401) {
        return {
          title: 'Authentication Error',
          message: error.message,
          severity: 'error' as const,
          suggestion: 'Please check your Anthropic API key in the environment variables.',
          canRetry: false
        };
      }
      
      if (error.statusCode === 429) {
        return {
          title: 'Rate Limit Exceeded',
          message: error.message,
          severity: 'warning' as const,
          suggestion: 'Please wait a moment and try again, or check your API usage limits.',
          canRetry: true
        };
      }
      
      if (error.statusCode === 402) {
        return {
          title: 'API Quota Exceeded',
          message: error.message,
          severity: 'error' as const,
          suggestion: 'Please check your Anthropic account billing status and add credits if needed.',
          canRetry: false
        };
      }
      
      return {
        title: 'API Error',
        message: error.message,
        severity: 'error' as const,
        suggestion: 'Please try again. If the problem persists, contact support.',
        canRetry: true
      };
    }
    
    if (error instanceof ValidationError) {
      return {
        title: 'Invalid Input',
        message: error.message,
        severity: 'warning' as const,
        suggestion: 'Please check the URL and ensure it points to a valid article.',
        canRetry: false
      };
    }
    
    if (error instanceof ClaudeServiceError) {
      return {
        title: 'Service Error',
        message: error.message,
        severity: 'error' as const,
        suggestion: 'Please try again. If the problem persists, contact support.',
        canRetry: true
      };
    }
    
    // Generic error
    return {
      title: 'Unexpected Error',
      message: error.message || 'An unexpected error occurred',
      severity: 'error' as const,
      suggestion: 'Please try again or contact support if the problem persists.',
      canRetry: true
    };
  }, []);

  const handleError = useCallback((error: Error) => {
    const details = getErrorDetails(error);
    setErrorState({
      error,
      isErrorVisible: true,
      errorDetails: details
    });

    // Log error for debugging
    console.error('Error handled:', {
      error,
      details,
      stack: error.stack
    });
  }, [getErrorDetails]);

  const clearError = useCallback(() => {
    setErrorState({
      error: null,
      isErrorVisible: false,
      errorDetails: null
    });
  }, []);

  const hideError = useCallback(() => {
    setErrorState(prev => ({
      ...prev,
      isErrorVisible: false
    }));
  }, []);

  return {
    errorState,
    handleError,
    clearError,
    hideError
  };
};

export default useErrorHandler;