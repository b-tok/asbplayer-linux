import { isFirefoxBuild } from './build-flags';

/**
 * Browser-agnostic sidebar service that abstracts Chrome's sidePanel API
 * and Firefox's sidebarAction API into a unified interface.
 */
export class SidebarService {
    /**
     * Opens the sidebar/side panel in the current window.
     * - Chrome: Uses chrome.sidePanel.open()
     * - Firefox: Uses browser.sidebarAction.open()
     */
    static async open(): Promise<void> {
        if (isFirefoxBuild) {
            // Firefox sidebarAction API
            await browser.sidebarAction.open();
        } else {
            // Chrome sidePanel API (requires Chrome 116+)
            const window = await browser.windows.getLastFocused();
            // @ts-ignore - sidePanel API not in types yet
            await browser.sidePanel.open({ windowId: window.id });
        }
    }

    /**
     * Closes the sidebar/side panel.
     * - Chrome: Sends message to side panel to close itself
     * - Firefox: Uses browser.sidebarAction.close()
     */
    static async close(): Promise<void> {
        if (isFirefoxBuild) {
            // Firefox sidebarAction API
            await browser.sidebarAction.close();
        } else {
            // Chrome doesn't have a direct close API
            // The side panel must close itself or user must close it manually
            // We handle closing via message passing in the toggle handler
            console.warn('Chrome side panel close() called - not directly supported');
        }
    }

    /**
     * Toggles the sidebar/side panel open or closed.
     * - Chrome: Custom implementation via message passing
     * - Firefox: Uses browser.sidebarAction.toggle()
     */
    static async toggle(): Promise<void> {
        if (isFirefoxBuild) {
            // Firefox sidebarAction API has built-in toggle
            await browser.sidebarAction.toggle();
        } else {
            // Chrome requires custom toggle logic
            // This is handled by the toggle-side-panel-handler
            throw new Error('Chrome toggle should be handled by toggle-side-panel-handler');
        }
    }

    /**
     * Checks if the sidebar/side panel is currently open.
     * - Chrome: No direct API, returns false
     * - Firefox: Uses browser.sidebarAction.isOpen()
     */
    static async isOpen(): Promise<boolean> {
        if (isFirefoxBuild) {
            // Firefox sidebarAction API
            return await browser.sidebarAction.isOpen({});
        } else {
            // Chrome doesn't provide a direct way to check
            // The extension tracks this via message passing
            return false;
        }
    }

    /**
     * Sets the sidebar panel (HTML page) to display.
     * - Chrome: Uses chrome.sidePanel.setOptions()
     * - Firefox: Uses browser.sidebarAction.setPanel()
     */
    static async setPanel(panelPath: string): Promise<void> {
        if (isFirefoxBuild) {
            // Firefox sidebarAction API
            await browser.sidebarAction.setPanel({ panel: panelPath });
        } else {
            // Chrome sidePanel API
            // @ts-ignore - sidePanel API not in types yet
            await browser.sidePanel.setOptions({ path: panelPath });
        }
    }

    /**
     * Sets the title of the sidebar/side panel.
     * - Chrome: Uses chrome.sidePanel.setOptions()
     * - Firefox: Uses browser.sidebarAction.setTitle()
     */
    static async setTitle(title: string): Promise<void> {
        if (isFirefoxBuild) {
            // Firefox sidebarAction API
            await browser.sidebarAction.setTitle({ title });
        } else {
            // Chrome doesn't support setting side panel title dynamically
            console.warn('Chrome side panel setTitle() not supported');
        }
    }
}
