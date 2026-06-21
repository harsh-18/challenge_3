import React from 'react';

/**
 * React Error Boundary component for graceful crash recovery.
 * Catches JavaScript errors anywhere in its child component tree,
 * logs them, and displays a fallback UI instead of crashing the entire app.
 */
class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }

  componentDidCatch(error, errorInfo) {
    console.error('ErrorBoundary caught an error:', error, errorInfo);
  }

  handleRetry = () => {
    this.setState({ hasError: false, error: null });
  };

  render() {
    if (this.state.hasError) {
      return (
        <div
          role="alert"
          aria-live="assertive"
          className="error-boundary-fallback"
        >
          <div className="error-boundary-content">
            <div className="error-boundary-icon" aria-hidden="true">⚠️</div>
            <h2>Something went wrong</h2>
            <p>
              An unexpected error occurred. Please try refreshing the page or click
              the button below to retry.
            </p>
            <button
              onClick={this.handleRetry}
              className="btn-primary"
              style={{ marginTop: '16px' }}
            >
              Try Again
            </button>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}

export default ErrorBoundary;
