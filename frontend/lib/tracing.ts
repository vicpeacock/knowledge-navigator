/**
 * Frontend Tracing Module
 * Provides trace ID generation and logging for correlating frontend-backend requests
 */

// Generate a unique trace ID
export function generateTraceId(): string {
  // Use timestamp + random for uniqueness
  const timestamp = Date.now().toString(36);
  const random = Math.random().toString(36).substring(2, 9);
  return `frontend-${timestamp}-${random}`;
}

// Get current trace ID from session storage or generate new one
export function getCurrentTraceId(): string {
  if (typeof window === 'undefined') {
    return generateTraceId();
  }

  try {
    // Try to get existing trace ID from session storage
    let traceId = sessionStorage.getItem('current_trace_id');
    
    if (!traceId) {
      traceId = generateTraceId();
      try {
        sessionStorage.setItem('current_trace_id', traceId);
      } catch (e) {
        // If sessionStorage is not available (e.g., private browsing), continue without storing
        console.warn('Failed to store trace ID in sessionStorage:', e);
      }
    }
    
    return traceId;
  } catch (error) {
    // If sessionStorage fails, generate a new trace ID without storing
    console.warn('Failed to get trace ID from sessionStorage:', error);
    return generateTraceId();
  }
}

// Set a new trace ID (for new user actions)
export function setNewTraceId(): string {
  const traceId = generateTraceId();
  if (typeof window !== 'undefined') {
    try {
      sessionStorage.setItem('current_trace_id', traceId);
    } catch (e) {
      // If sessionStorage is not available, continue without storing
      console.warn('Failed to store new trace ID in sessionStorage:', e);
    }
  }
  return traceId;
}

// Log with trace ID
export function logWithTrace(traceId: string, message: string, level: 'info' | 'warn' | 'error' = 'info', data?: any): void {
  const logMessage = `[Trace: ${traceId}] ${message}`;
  
  if (data) {
    switch (level) {
      case 'error':
        console.error(logMessage, data);
        break;
      case 'warn':
        console.warn(logMessage, data);
        break;
      default:
        console.log(logMessage, data);
    }
  } else {
    switch (level) {
      case 'error':
        console.error(logMessage);
        break;
      case 'warn':
        console.warn(logMessage);
        break;
      default:
        console.log(logMessage);
    }
  }
}

// Track API request
export function trackApiRequest(
  method: string,
  url: string,
  traceId: string,
  startTime: number
): void {
  if (process.env.NODE_ENV === 'development') {
    logWithTrace(traceId, `API Request: ${method} ${url}`, 'info');
  }
}

// Track API response
export function trackApiResponse(
  method: string,
  url: string,
  traceId: string,
  status: number,
  duration: number,
  error?: any
): void {
  if (error) {
    logWithTrace(
      traceId,
      `API Error: ${method} ${url} - ${status} (${duration}ms)`,
      'error',
      error
    );
  } else {
    if (process.env.NODE_ENV === 'development') {
      logWithTrace(
        traceId,
        `API Response: ${method} ${url} - ${status} (${duration}ms)`,
        'info'
      );
    }
  }
}

// Track user interaction
export function trackUserInteraction(
  action: string,
  component?: string,
  data?: any
): void {
  const traceId = getCurrentTraceId();
  
  if (process.env.NODE_ENV === 'development') {
    logWithTrace(
      traceId,
      `User Interaction: ${action}${component ? ` (${component})` : ''}`,
      'info',
      data
    );
  }
}

// Track page load
export function trackPageLoad(pageName: string, loadTime: number): void {
  const traceId = getCurrentTraceId();
  
  if (process.env.NODE_ENV === 'development') {
    logWithTrace(
      traceId,
      `Page Load: ${pageName} (${loadTime}ms)`,
      'info'
    );
  }
}

// Track error
export function trackError(
  error: Error | string,
  context?: string,
  data?: any
): void {
  const traceId = getCurrentTraceId();
  const errorMessage = error instanceof Error ? error.message : error;
  
  logWithTrace(
    traceId,
    `Error${context ? ` in ${context}` : ''}: ${errorMessage}`,
    'error',
    {
      error: error instanceof Error ? {
        name: error.name,
        message: error.message,
        stack: error.stack
      } : error,
      context,
      ...data
    }
  );
}

// Performance measurement helper
export class PerformanceTracker {
  private startTime: number;
  private traceId: string;
  private name: string;

  constructor(name: string) {
    this.name = name;
    this.traceId = getCurrentTraceId();
    this.startTime = performance.now();
  }

  end(): number {
    const duration = performance.now() - this.startTime;
    
    if (process.env.NODE_ENV === 'development') {
      logWithTrace(
        this.traceId,
        `Performance: ${this.name} (${duration.toFixed(2)}ms)`,
        'info'
      );
    }
    
    return duration;
  }

  mark(eventName: string): void {
    const elapsed = performance.now() - this.startTime;
    
    if (process.env.NODE_ENV === 'development') {
      logWithTrace(
        this.traceId,
        `Performance Mark: ${this.name} - ${eventName} (${elapsed.toFixed(2)}ms)`,
        'info'
      );
    }
  }
}

