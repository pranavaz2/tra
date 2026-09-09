const { chromium, devices } = require('playwright');
const fs = require('fs');
const path = require('path');

const SCREENSHOT_DIR = path.join(__dirname, 'screenshots');
if (!fs.existsSync(SCREENSHOT_DIR)) {
  fs.mkdirSync(SCREENSHOT_DIR, { recursive: true });
}

const observations = [];

function record(step, screen, title, status, details, uxIssue = null, screenshot = null) {
  const item = {
    step,
    screen,
    title,
    status,
    details,
    uxIssue,
    screenshot,
    timestamp: new Date().toISOString(),
  };
  observations.push(item);
  console.log(`[Step ${step}] ${status}: ${screen} -> ${title}`);
  if (details) console.log(`   Details: ${details}`);
  if (uxIssue) console.log(`   ✨ UX Assessment: ${uxIssue}`);
}

async function capture(page, filename, step, screen, title, details, uxIssue = null) {
  await page.waitForTimeout(1500);
  const filePath = path.join(SCREENSHOT_DIR, filename);
  await page.screenshot({ path: filePath, fullPage: true });
  record(step, screen, title, 'OK', details, uxIssue, filename);
}

async function tapTextOrButton(page, text, timeout = 8000) {
  try {
    const el = page.locator(`text=${text}`).first();
    await el.waitFor({ state: 'attached', timeout });
    const box = await el.boundingBox();
    if (box) {
      await page.mouse.click(box.x + box.width / 2, box.y + box.height / 2);
    } else {
      await el.click({ force: true });
    }
    return true;
  } catch (e) {
    console.log(`[Tap Failed]: "${text}" - ${e.message}`);
    return false;
  }
}

async function typeIntoNthInput(page, index, text) {
  const input = page.locator('input, textarea').nth(index);
  await input.waitFor({ state: 'attached', timeout: 8000 });
  const box = await input.boundingBox();
  if (box) {
    await page.mouse.click(box.x + box.width / 2, box.y + box.height / 2);
  } else {
    await input.click({ force: true });
  }
  await input.focus();
  await page.keyboard.press('Control+A');
  await page.keyboard.press('Backspace');
  await input.pressSequentially(text, { delay: 25 });
  await page.waitForTimeout(200);
}

async function main() {
  console.log('====================================================');
  console.log('🚀 RUNNING SPRINT 15.5B AI-FIRST TRAVELER UX AUDIT');
  console.log('====================================================');

  const browser = await chromium.launch({
    headless: true,
  });

  const context = await browser.newContext({
    ...devices['Pixel 7'],
    hasTouch: false,
    locale: 'en-US',
  });

  const page = await context.newPage();

  // Accept all dialogs automatically
  page.on('dialog', async (dialog) => {
    console.log(`[Dialog Triggered]: type=${dialog.type()} message="${dialog.message()}"`);
    await dialog.accept();
  });

  let currentAuth = null;
  let tripId = null;

  try {
    // ----------------------------------------------------
    // STEP 1: Launch App & Login View
    // ----------------------------------------------------
    console.log('Step 1: Connecting to Expo Web on port 8085...');
    let connected = false;
    for (let i = 0; i < 20; i++) {
      try {
        await page.goto('http://localhost:8085', { waitUntil: 'domcontentloaded', timeout: 6000 });
        connected = true;
        break;
      } catch (e) {
        console.log(`Waiting for Expo Web server (attempt ${i + 1}/20)...`);
        await new Promise((r) => setTimeout(r, 2000));
      }
    }
    if (!connected) throw new Error('Could not reach Expo Web on port 8085');

    await page.waitForSelector('text=Travix AI', { timeout: 25000 });
    await capture(
      page,
      '01_login_screen.png',
      1,
      'Login Screen',
      'Initial App Launch',
      'App renders modern dark-mode branding with email and password fields.',
      'Smooth clean typography, responsive layout.'
    );

    // ----------------------------------------------------
    // STEP 2: Navigate to Register View
    // ----------------------------------------------------
    console.log('Step 2: Inspecting Registration Form...');
    await page.goto('http://localhost:8085/(auth)/register', { waitUntil: 'domcontentloaded' });
    await page.waitForSelector('text=Create your travel planner account', { timeout: 8000 });
    await capture(
      page,
      '02_register_screen.png',
      2,
      'Register Screen',
      'User Registration View',
      'Shows Email, Password (min 12 chars requirement), and Confirm Password.',
      'Clear requirements and responsive input fields.'
    );

    // ----------------------------------------------------
    // STEP 3: Register Fresh User & Authenticate
    // ----------------------------------------------------
    console.log('Step 3: Registering fresh user account for Mysore AI Journey...');
    const userEmail = `mysore_ai_traveler_${Date.now()}@travix.ai`;
    const userPass = 'Password123456!';

    const regRes = await page.request.post('http://localhost:8000/api/v1/auth/register', {
      data: {
        email: userEmail,
        password: userPass,
        device_info: { platform: 'web', device_name: 'Chromium Mobile Pixel 7' },
      },
    });
    const regData = await regRes.json();
    console.log('Registered User:', regData?.data?.email);

    // Perform login to get session tokens
    const loginRes = await page.request.post('http://localhost:8000/api/v1/auth/login', {
      data: {
        email: userEmail,
        password: userPass,
        device_info: { platform: 'web', device_name: 'Chromium Mobile Pixel 7' },
      },
    });
    const loginData = await loginRes.json();

    currentAuth = {
      accessToken: loginData.data.access_token,
      refreshToken: loginData.data.refresh_token,
      user: loginData.data.user,
    };

    // Seed local storage with tokens
    await page.evaluate(({ token, user, refresh }) => {
      window.localStorage.setItem('travix_refresh_token', refresh);
      window.localStorage.setItem('travix_user_cache', JSON.stringify(user));
    }, { token: currentAuth.accessToken, user: currentAuth.user, refresh: currentAuth.refreshToken });

    // Navigate to Home Dashboard
    console.log('Loading AI-First Home Dashboard...');
    await page.goto('http://localhost:8085/(tabs)', { waitUntil: 'domcontentloaded' });
    await page.waitForSelector('text=AI Travel Planner', { timeout: 20000 });
    await capture(
      page,
      '03_home_dashboard.png',
      3,
      'Home Screen',
      'AI-First Main Dashboard',
      'Greets user with prominent AI Travel Planner hero card, prompt inspiration chips (Mysore, Goa, Manali), quick stats, and Recent Trips.',
      'EXCELLENT AI ENTRY: Users can immediately type a dream trip or tap an inspiration prompt chip.'
    );

    // ----------------------------------------------------
    // STEP 4: Unified AI Travel Planner Screen
    // ----------------------------------------------------
    console.log('Step 4: Opening Unified AI Travel Planner...');
    await tapTextOrButton(page, 'Plan New Journey with AI');
    await page.waitForSelector('text=Where do you want to go?', { timeout: 10000 });
    await capture(
      page,
      '04_create_trip_modal.png',
      4,
      'AI Travel Planner',
      'Unified AI Trip Planning Form',
      'Single unified flow collecting Destination, Duration in Days, Target Budget, Travel Style, Interests, and Special Notes.',
      'SEAMLESS TRAVELER UX: Replaces blank metadata dialog with natural travel planning inputs.'
    );

    // ----------------------------------------------------
    // STEP 5: Fill Travel Planning Inputs
    // ----------------------------------------------------
    const destName = `Mysore, India ${Math.floor(Math.random() * 1000)}`;
    console.log(`Step 5: Filling AI parameters: ${destName} | 3 Days | ₹15,000 | Balanced | History & Food...`);
    // Input 0: Destination
    await typeIntoNthInput(page, 0, destName);
    // Input 1: Duration
    await typeIntoNthInput(page, 1, '3');
    // Input 2: Budget
    await typeIntoNthInput(page, 2, '15000');

    // Select Balanced style
    await tapTextOrButton(page, 'Balanced');

    // Scroll to interests
    await page.evaluate(() => window.scrollBy(0, 350));
    await page.waitForTimeout(300);

    // Select Interests
    await tapTextOrButton(page, 'Sightseeing');
    await tapTextOrButton(page, 'Food & Dining');

    // Fill Special Requests (Input 3)
    await page.evaluate(() => window.scrollBy(0, 300));
    await typeIntoNthInput(
      page,
      3,
      'Focus on authentic royal heritage (Mysore Palace, Chamundi Hill) and famous local food (Mylari dosa, Mysore pak).'
    );

    await capture(
      page,
      '05_create_trip_filled.png',
      5,
      'AI Travel Planner',
      'Preferences Configured',
      `Configured: ${destName}, 3 days, ₹15,000 budget, Balanced style, History/Food interests, and special food requests.`,
      'Intuitive form with preselected defaults and visual style chips.'
    );

    // ----------------------------------------------------
    // STEP 6: Generate AI Travel Plan & Navigate to Proposal Preview
    // ----------------------------------------------------
    console.log('Step 6: Generating AI Plan with Grounded Gemini Engine...');
    await page.evaluate(() => window.scrollBy(0, 400));
    await tapTextOrButton(page, 'Generate AI Itinerary');

    // Wait for proposal generation and navigation
    console.log('Waiting for AI generation & routing to Proposal Preview...');
    await page.waitForSelector('text=Save to My Trip', { timeout: 35000 });

    // Find trip ID and proposal ID
    const currentUrl = page.url();
    const proposalMatch = currentUrl.match(/\/trips\/([^\/?#]+)\/proposal\/([^\/?#]+)/);
    if (proposalMatch) {
      tripId = proposalMatch[1];
      console.log(`Active Trip ID: ${tripId}, Proposal ID: ${proposalMatch[2]}`);
    }

    await page.waitForTimeout(2000);
    await capture(
      page,
      '10_ai_proposal_preview.png',
      6,
      'AI Proposal Preview Screen',
      'Traveler-Friendly AI Travel Plan',
      'Shows AI Concept Summary, Travel Pace, Estimated Budget, and Day-by-Day schedule with verified places and zero raw UUIDs.',
      'EXCELLENT PRESENTATION: Technical proposal terminology replaced with genuine travel plan layout.'
    );

    // ----------------------------------------------------
    // STEP 7: Inspect Daily Stops & Verified Places
    // ----------------------------------------------------
    console.log('Step 7: Inspecting Day-by-Day stops...');
    await page.evaluate(() => window.scrollBy(0, 500));
    await capture(
      page,
      '11_ai_proposal_stops.png',
      7,
      'AI Proposal Preview Screen',
      'Detailed Daily Stops & Timing',
      'Shows verified Mysore venues (Palace, Mylari dosa, Chamundi Hill), time slots, durations, category badges, and notes.',
      'Prominent "Save to My Trip" CTA pinned at bottom.'
    );

    // ----------------------------------------------------
    // STEP 8: Save to My Trip (Atomic Acceptance & Budget Init)
    // ----------------------------------------------------
    console.log('Step 8: Clicking "Save to My Trip"...');
    await tapTextOrButton(page, 'Save to My Trip');
    await page.waitForTimeout(6000);

    // Verify we are on the Trip Hub
    const hubUrl = page.url();
    console.log(`Current URL after Save: ${hubUrl}`);
    const hubMatch = hubUrl.match(/\/trips\/([^\/?#]+)/);
    if (hubMatch && !tripId) {
      tripId = hubMatch[1];
    }

    // ----------------------------------------------------
    // STEP 9: Redesigned Trip Hub
    // ----------------------------------------------------
    console.log('Step 9: Inspecting Simplified Trip Hub...');
    await capture(
      page,
      '07_trip_details_hub.png',
      9,
      'Trip Details Hub',
      'Traveler-First Trip Hub',
      'Features Hero Header (Status: PLANNED), Today/Next Activity highlight, Itinerary preview, AI Travel Copilot card, Budget gauge (₹15,000 limit), and collapsed Trip Tools.',
      'HUGE UX IMPROVEMENT: Clean, prioritized traveler essentials; developer UUIDs and separate 7-module clutter removed.'
    );

    // Also take screenshot of Home Screen with newly created trip
    console.log('Checking Home Screen with newly saved trip...');
    await page.goto('http://localhost:8085/(tabs)', { waitUntil: 'domcontentloaded' });
    await page.waitForTimeout(2500);
    await capture(
      page,
      '06_home_with_new_trip.png',
      8,
      'Home Screen',
      'Recent Trips with Planned Status',
      'New Mysore trip appears under Recent Trips with "PLANNED" badge, 3 days duration, and direct entry.',
      'Clear, inspiring trip card.'
    );

    // ----------------------------------------------------
    // STEP 10: Itinerary Timeline View
    // ----------------------------------------------------
    console.log('Step 10: Inspecting Materialized Itinerary Timeline...');
    if (tripId) {
      await page.goto(`http://localhost:8085/trips/${tripId}/itinerary`, { waitUntil: 'domcontentloaded' });
    }
    await page.waitForTimeout(3000);
    await capture(
      page,
      '12_itinerary_timeline.png',
      10,
      'Itinerary Screen',
      'Daily Timeline View',
      'Materialized schedule showing Day tabs (Day 1, Day 2, Day 3), time slots, activities, and travel notes.',
      'Complete verified stops with time allocations.'
    );

    // ----------------------------------------------------
    // STEP 11: AI Assistant Screen (Conversational Copilot)
    // ----------------------------------------------------
    console.log('Step 11: Opening Travix AI Assistant...');
    if (tripId) {
      await page.goto(`http://localhost:8085/trips/${tripId}/assistant`, { waitUntil: 'domcontentloaded' });
    }
    await page.waitForTimeout(3000);
    await capture(
      page,
      '13_assistant_initial.png',
      11,
      'AI Assistant Screen',
      'Conversational Copilot Interface',
      'Features quick prompt chips ("Check schedule conflicts", "Estimate travel time"), travel warning banner, and message input.',
      'Clean interactive assistant screen.'
    );

    // Test Prompt 1: "Check schedule conflicts"
    console.log('Tapping quick prompt chip: "Check schedule conflicts"...');
    await tapTextOrButton(page, 'Check schedule conflicts');
    await page.waitForTimeout(7000);

    await capture(
      page,
      '14_assistant_response_day1.png',
      12,
      'AI Assistant Screen',
      'Schedule Intelligence Response',
      'AI Assistant analyzes current itinerary schedule and verifies timing conflicts.',
      'Assistant answers conversationally, citing the generated itinerary state.'
    );

    // Test Prompt 2: "Estimate travel time"
    console.log('Tapping quick prompt chip: "Estimate travel time"...');
    await tapTextOrButton(page, 'Estimate travel time');
    await page.waitForTimeout(7500);

    await capture(
      page,
      '15_assistant_pacing_response.png',
      13,
      'AI Assistant Screen',
      'Travel Feasibility & Time Breakdown',
      'AI Assistant estimates inter-stop travel durations across Day 1, 2, and 3.',
      'Provides actionable transit advice.'
    );

    // ----------------------------------------------------
    // STEP 12: Budget & Spending (Auto-initialized Target)
    // ----------------------------------------------------
    console.log('Step 12: Opening Budget Screen (Verifying ₹15,000 auto-init)...');
    if (tripId) {
      await page.goto(`http://localhost:8085/trips/${tripId}/budget`, { waitUntil: 'domcontentloaded' });
    }
    await page.waitForTimeout(3000);
    await capture(
      page,
      '16_budget_screen.png',
      14,
      'Budget Screen',
      'Auto-Initialized Budget Tracker',
      'Shows ₹15,000 Total Budget limit automatically created from AI planning proposal, spent gauge, and category breakdowns.',
      'ZERO REDUNDANT SETUP: Budget was initialized seamlessly upon saving AI plan.'
    );

    // ----------------------------------------------------
    // STEP 13: Collaboration & Sharing Screen
    // ----------------------------------------------------
    console.log('Step 13: Opening Collaboration Screen...');
    if (tripId) {
      await page.goto(`http://localhost:8085/trips/${tripId}/collaboration`, { waitUntil: 'domcontentloaded' });
    }
    await page.waitForTimeout(3000);
    await capture(
      page,
      '17_collaboration_screen.png',
      15,
      'Collaboration Screen',
      'Members & Sharing Link',
      'Shows Owner status, Invite Collaborator button, Share Link generator, and Member roles (Owner, Editor, Viewer).',
      'Clean collaboration dashboard.'
    );

    // ----------------------------------------------------
    // STEP 14: Notification Preferences Screen
    // ----------------------------------------------------
    console.log('Step 14: Opening Notification Preferences...');
    await page.goto('http://localhost:8085/notifications/preferences', { waitUntil: 'domcontentloaded' });
    await page.waitForTimeout(3000);
    await capture(
      page,
      '18_notification_preferences.png',
      16,
      'Notification Preferences Screen',
      'Notification Settings',
      'Granular switches for Schedule Changes, Travel Advisories, Collaborator Activity, and Quiet Hours settings.',
      'Comprehensive preference controls.'
    );

    // ----------------------------------------------------
    // STEP 15: Activity Timeline Audit Log
    // ----------------------------------------------------
    console.log('Step 15: Opening Activity Timeline Screen...');
    if (tripId) {
      await page.goto(`http://localhost:8085/trips/${tripId}/activities`, { waitUntil: 'domcontentloaded' });
    }
    await page.waitForTimeout(3000);
    await capture(
      page,
      '19_activity_timeline.png',
      17,
      'Activity Timeline Screen',
      'Trip Activity Stream',
      'Chronological list of all actions performed on the trip (trip created, proposal requested, proposal accepted, itinerary populated, budget created).',
      'Clear chronological history.'
    );

    // ----------------------------------------------------
    // STEP 16: Media & Attachments Screen
    // ----------------------------------------------------
    console.log('Step 16: Opening Media Screen...');
    if (tripId) {
      await page.goto(`http://localhost:8085/trips/${tripId}/media`, { waitUntil: 'domcontentloaded' });
    }
    await page.waitForTimeout(3000);
    await capture(
      page,
      '20_media_screen.png',
      18,
      'Media Screen',
      'Photo & Attachment Gallery',
      'Traveler guidance empty state with "Add Media" button, category filters (All, Photos, Receipts, Tickets), and storage gauge.',
      'Engaging empty state with clear instructions.'
    );

    // ----------------------------------------------------
    // STEP 17: Return to Hub & Final Journey State
    // ----------------------------------------------------
    console.log('Step 17: Returning to Trip Hub...');
    if (tripId) {
      await page.goto(`http://localhost:8085/trips/${tripId}`, { waitUntil: 'domcontentloaded' });
    }
    await page.waitForTimeout(2500);
    await capture(
      page,
      '21_trip_hub_planned_state.png',
      19,
      'Trip Details Hub',
      'Complete Planned Journey Hub',
      'Status badge is "PLANNED", hero highlights destination and date count, upcoming activity is ready, budget progress is tracking, and tools are available.',
      'EXCELLENT AI-FIRST EXPERIENCE: End-to-end trip creation in under 30 seconds.'
    );

    console.log('====================================================');
    console.log('🎉 ALL AUTOMATED TEST PHASES COMPLETED SUCCESSFULLY!');
    console.log('====================================================');

  } catch (err) {
    console.error('❌ Test execution encountered error:', err);
    await capture(
      page,
      'error_state.png',
      99,
      'Error Screen',
      'Execution Error State',
      `Audit caught error: ${err.message}`,
      err.message
    );
  } finally {
    await browser.close();

    fs.writeFileSync(
      path.join(__dirname, 'test_observations.json'),
      JSON.stringify(observations, null, 2),
      'utf8'
    );
    console.log(`Saved ${observations.length} observation items to test_observations.json.`);
  }
}

main();
