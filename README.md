# FrogFindNG

FrogFindNG is a fork of [FrogFind](https://github.com/ActionRetro/FrogFind), designed to provide a simple and lightweight interface to access the modern web, optimized for various compatibility levels including retro and ultra-retro systems. It simplifies web content to make it accessible for older browsers and low-resource devices, while offering a clean and user-friendly experience.

## Features

- **Simplified Web Access**: Strips away complex elements (e.g., scripts, ads, navigation bars) to deliver clean, readable content.
- **Compatibility Modes**:
  - **Modern**: For contemporary browsers with full CSS and image support.
  - **Retro**: Optimized for older browsers like IE5/6 or Netscape 6.
  - **Ultra-Retro**: Text-only mode for extremely limited systems (e.g., Netscape 4, IE 3).
- **Dark Mode**: Optional dark theme for better readability in low-light conditions.
- **Search Integration**: Uses DuckDuckGo's HTML search for lightweight web searches.
- **Caching**: Implements Flask-Caching to store processed pages for 15 minutes, improving performance.
- **Customizable Interface**: Allows users to toggle compatibility modes and dark mode via a simple options panel.

## Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/RayTrunk/FrogFindNG.git
   cd FrogFindNG

Install dependencies:
bash
pip install flask flask-caching requests beautifulsoup4 readability-lxml

Run the application:
bash
python app.py
Access FrogFindNG at http://localhost:5000.

Usage:

Home Page: Enter a URL directly to read a simplified version of a webpage or use the search bar to find content via DuckDuckGo.
Compatibility Mode: Select from Modern, Retro, or Ultra-Retro modes to match your device's capabilities.
Dark Mode: Enable for a darker, eye-friendly interface.
Search Results: Click on search results to view simplified versions of web pages.
Direct URL Access: Input a URL to render a cleaned-up version of the page, with links rewritten to stay within FrogFindNG.
Technical Details
Framework: Built with Flask for a lightweight web server.
Content Processing:
Uses readability-lxml to extract main content from web pages.
BeautifulSoup cleans HTML by removing scripts, ads, and unnecessary elements.
Links are rewritten to route through FrogFindNG for consistent rendering.
Compatibility Detection: Automatically detects user agent to select the appropriate rendering mode, with manual override options.
Caching: Utilizes Flask-Caching with a 15-minute timeout to reduce server load.
License: GNU General Public License v3.0 (see LICENSE).
Contributing
Contributions are welcome! Please fork the repository, make your changes, and submit a pull request. Ensure your code adheres to the GPL-3.0 license.

Credits
Forked from ActionRetro/FrogFind.
Built with open-source libraries: Flask, BeautifulSoup, readability-lxml, and Flask-Caching.
Search powered by DuckDuckGo's HTML interface.
License
This project is licensed under the GNU General Public License v3.0. See the LICENSE file for details.

© 2025 RayTrunk
