/**
 * Test Helper Utilities
 *
 * Reusable helpers for integration tests
 */

import { waitFor } from '@testing-library/react';

/**
 * Wait for element to appear with custom timeout
 */
export const waitForElement = async (
  callback: () => HTMLElement | null,
  timeout = 3000
) => {
  return waitFor(callback, { timeout });
};

/**
 * Wait for API call to complete
 */
export const waitForApiCall = async (timeout = 1000) => {
  await new Promise(resolve => setTimeout(resolve, timeout));
};

/**
 * Simulate user typing with delay
 */
export const typeWithDelay = async (
  element: HTMLElement,
  text: string,
  delay = 50
) => {
  for (const char of text) {
    element.focus();
    (element as HTMLInputElement).value += char;
    element.dispatchEvent(new Event('input', { bubbles: true }));
    await new Promise(resolve => setTimeout(resolve, delay));
  }
};

/**
 * Wait for loading state to finish
 */
export const waitForLoadingToFinish = async (
  getLoadingElement: () => HTMLElement | null,
  timeout = 5000
) => {
  await waitFor(
    () => {
      const loading = getLoadingElement();
      if (loading) throw new Error('Still loading');
    },
    { timeout }
  );
};

/**
 * Wait for multiple conditions to be true
 */
export const waitForConditions = async (
  conditions: Array<() => boolean>,
  timeout = 3000
) => {
  const startTime = Date.now();

  while (Date.now() - startTime < timeout) {
    if (conditions.every(condition => condition())) {
      return;
    }
    await new Promise(resolve => setTimeout(resolve, 50));
  }

  throw new Error('Timeout waiting for conditions');
};

/**
 * Simulate network delay
 */
export const simulateNetworkDelay = async (ms = 100) => {
  await new Promise(resolve => setTimeout(resolve, ms));
};

/**
 * Wait for element to disappear
 */
export const waitForElementToDisappear = async (
  callback: () => HTMLElement | null,
  timeout = 3000
) => {
  return waitFor(
    () => {
      const element = callback();
      if (element) throw new Error('Element still present');
    },
    { timeout }
  );
};

/**
 * Wait for text content to match
 */
export const waitForTextContent = async (
  element: HTMLElement,
  expectedText: string | RegExp,
  timeout = 3000
) => {
  return waitFor(
    () => {
      const text = element.textContent || '';
      const matches = typeof expectedText === 'string'
        ? text.includes(expectedText)
        : expectedText.test(text);

      if (!matches) {
        throw new Error(`Expected text "${expectedText}" not found in "${text}"`);
      }
    },
    { timeout }
  );
};

/**
 * Wait for attribute to match
 */
export const waitForAttribute = async (
  element: HTMLElement,
  attribute: string,
  expectedValue: string,
  timeout = 3000
) => {
  return waitFor(
    () => {
      const value = element.getAttribute(attribute);
      if (value !== expectedValue) {
        throw new Error(`Expected ${attribute}="${expectedValue}", got "${value}"`);
      }
    },
    { timeout }
  );
};

/**
 * Wait for class to be present
 */
export const waitForClass = async (
  element: HTMLElement,
  className: string,
  timeout = 3000
) => {
  return waitFor(
    () => {
      if (!element.classList.contains(className)) {
        throw new Error(`Class "${className}" not found`);
      }
    },
    { timeout }
  );
};

/**
 * Wait for specific number of elements
 */
export const waitForElementCount = async (
  container: HTMLElement,
  selector: string,
  expectedCount: number,
  timeout = 3000
) => {
  return waitFor(
    () => {
      const elements = container.querySelectorAll(selector);
      if (elements.length !== expectedCount) {
        throw new Error(`Expected ${expectedCount} elements, found ${elements.length}`);
      }
    },
    { timeout }
  );
};
