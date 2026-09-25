export type GuideAudience = "all" | "librarian" | "associate" | "auditor";

export type GuideCard = {
  title: string;
  audiences: GuideAudience[];
  path: string;
  steps: string[];
};

export type GuideSection = {
  id: string;
  number: string;
  title: string;
  intro: string;
  cards: GuideCard[];
  note: string;
};

export const guideStages = [
  ["01", "Open the daily session", "Librarian team", "Confirm that today's QR code is active and ready for display."],
  ["02", "Verify the visitor", "Google or guest flow", "Match a school account to a library profile or collect visitor details."],
  ["03", "Record the check-in", "System or librarian", "Save one visit and enforce the configured duplicate-scan window."],
  ["04", "Review attendance", "Librarian team", "Search, filter, and inspect the persistent attendance log."],
  ["05", "Report and audit", "Librarian or auditor", "Analyze trends, export records, and retain the source and actor history."],
] as const;

export const guideSections: GuideSection[] = [
  {
    id: "start",
    number: "01",
    title: "Getting started",
    intro: "Use the dashboard to confirm today's service status and move directly to the task you need.",
    cards: [
      {
        title: "Review today's activity",
        audiences: ["all"],
        path: "Library -> Dashboard",
        steps: [
          "Open Dashboard from the left sidebar.",
          "Review Check-ins Today, Unique Visitors, and Peak Check-in Hour.",
          "Use Today's Activity to confirm the latest recorded visits.",
          "Select View Attendance when you need the complete searchable log.",
        ],
      },
      {
        title: "Display the daily QR code",
        audiences: ["librarian", "associate"],
        path: "Dashboard -> Daily QR Code",
        steps: [
          "Open Dashboard and confirm that the Daily QR Code card contains a code.",
          "Select the QR display icon to open the entrance display.",
          "Use Fullscreen on the display device and keep the current date visible.",
          "Return to Dashboard when the display no longer needs to be shown.",
        ],
      },
      {
        title: "Switch appearance or sign out",
        audiences: ["all"],
        path: "Account menu -> Light mode / Dark mode / Sign out",
        steps: [
          "Select your account at the bottom of the sidebar.",
          "Choose Light mode or Dark mode for your preferred display.",
          "Check the name and role shown in the account panel.",
          "Select Sign out before leaving a shared workstation.",
        ],
      },
    ],
    note: "The daily QR code is replaced at midnight in the configured library timezone.",
  },
  {
    id: "checkins",
    number: "02",
    title: "Recording attendance",
    intro: "Visitors can scan the daily code, while authorized staff can record a manual check-in when needed.",
    cards: [
      {
        title: "Check in with a school account",
        audiences: ["all"],
        path: "Daily QR -> Library Check-In",
        steps: [
          "Scan the current QR code using a phone or tablet.",
          "Select Continue with Google and use a Life College account.",
          "Review the matched name, number, and library profile.",
          "Select Record Library Check-In and wait for the confirmation reference.",
        ],
      },
      {
        title: "Check in a visitor",
        audiences: ["all"],
        path: "Daily QR -> Check In as a Guest",
        steps: [
          "Scan the current QR code and choose the guest check-in option.",
          "Enter the visitor's full name and organization.",
          "Choose the purpose of the visit.",
          "Submit the form and keep the displayed reference if follow-up is needed.",
        ],
      },
      {
        title: "Record a manual check-in",
        audiences: ["librarian", "associate"],
        path: "Library -> Attendance -> Manual Check-In",
        steps: [
          "Open Attendance and select Manual Check-In.",
          "Search for the library user and confirm the correct profile.",
          "Use the current date and time, or enter an authorized adjustment with its reason.",
          "Save the check-in and confirm that it appears in the attendance table.",
        ],
      },
    ],
    note: "A repeated scan inside the configured duplicate window does not create another visit.",
  },
  {
    id: "attendance",
    number: "03",
    title: "Attendance and user records",
    intro: "Use the attendance log for visit events and Library Users for profile-level history.",
    cards: [
      {
        title: "Find an attendance record",
        audiences: ["all"],
        path: "Library -> Attendance",
        steps: [
          "Open Attendance from the left sidebar.",
          "Search by name or user number and apply the available filters.",
          "Review the date, check-in time, user type, and attendance source.",
          "Clear or change filters before starting a different search.",
        ],
      },
      {
        title: "Review a user's visit history",
        audiences: ["all"],
        path: "Library -> Library Users -> User Profile",
        steps: [
          "Open Library Users and search for the person by name or number.",
          "Select the correct row to open the profile.",
          "Review profile details and the chronological visit history.",
          "Return to Library Users to continue searching the roster.",
        ],
      },
      {
        title: "Create or update a library user",
        audiences: ["librarian"],
        path: "Library -> Library Users -> Add / Edit User",
        steps: [
          "Open Library Users and select Add User, or open an existing record for editing.",
          "Choose the correct user category and complete its required profile fields.",
          "Confirm the institutional email, user number, and organization details.",
          "Save the profile and verify that it appears in roster search.",
        ],
      },
    ],
    note: "Attendance records are institutional data; use only the minimum access needed for the task.",
  },
  {
    id: "reports",
    number: "04",
    title: "Reports and exports",
    intro: "Build a filtered view first, verify its coverage, and only then export the result.",
    cards: [
      {
        title: "Run a library usage report",
        audiences: ["all"],
        path: "Library -> Reports",
        steps: [
          "Open Reports and select the reporting period or custom date range.",
          "Apply user type, program, year level, section, or department filters as needed.",
          "Review totals, unique visitors, return visits, trends, and peak periods.",
          "Check that the displayed filters match the question the report must answer.",
        ],
      },
      {
        title: "Export to Excel or PDF",
        audiences: ["librarian", "associate", "auditor"],
        path: "Reports -> Export",
        steps: [
          "Complete and verify the report filters before exporting.",
          "Select the Excel export for a data workbook or PDF for a fixed report.",
          "Open the downloaded file and confirm the title, date range, filters, and totals.",
          "Store or share the export according to the approved privacy and retention policy.",
        ],
      },
    ],
    note: "Exports reflect the active report filters and should be checked before distribution.",
  },
  {
    id: "administration",
    number: "05",
    title: "Administration",
    intro: "Administrative controls manage staff access and the shared library configuration.",
    cards: [
      {
        title: "Manage staff accounts",
        audiences: ["librarian", "associate"],
        path: "Administration -> Staff Accounts",
        steps: [
          "Open Staff Accounts from the left sidebar.",
          "Review the staff member's role and current account status.",
          "Create or update the account using the least-privilege role appropriate to the job.",
          "Confirm the saved account and communicate credentials through an approved channel.",
        ],
      },
      {
        title: "Update library settings",
        audiences: ["librarian"],
        path: "Administration -> Settings",
        steps: [
          "Open Settings and review the section related to the intended change.",
          "Update library operations, QR behavior, academic calendar, school structure, report defaults, or display text.",
          "Select Save Changes and wait for the saved confirmation.",
          "Review Audit History to confirm the actor and time of the update.",
        ],
      },
      {
        title: "Import the library roster",
        audiences: ["librarian"],
        path: "Library Users -> Roster Import",
        steps: [
          "Download or follow the approved roster template and preserve its column names.",
          "Check required identifiers, emails, user categories, and profile fields before import.",
          "Upload the CSV from Library Users and review validation results.",
          "Correct rejected rows and confirm the imported users through roster search.",
        ],
      },
    ],
    note: "Settings and account changes are shared operations; confirm the target and role before saving.",
  },
  {
    id: "troubleshooting",
    number: "06",
    title: "Troubleshooting and controls",
    intro: "Start with the displayed status or error, preserve the reference, and avoid creating duplicate records.",
    cards: [
      {
        title: "Resolve a QR check-in issue",
        audiences: ["librarian", "associate"],
        path: "Dashboard / Scan Screen",
        steps: [
          "Confirm that the displayed QR is for the current date and has not expired.",
          "Check whether the visitor has a stable connection and is using the intended account.",
          "If no active profile is linked, verify the user in Library Users before trying again.",
          "Use Manual Check-In only when appropriate and retain the adjustment reason.",
        ],
      },
      {
        title: "Investigate a duplicate or missing visit",
        audiences: ["librarian", "associate", "auditor"],
        path: "Attendance -> Search and Filters",
        steps: [
          "Search the attendance log by user number and the exact date.",
          "Review the check-in source, timestamp, and duplicate-window behavior.",
          "Check the user's visit history for the same event.",
          "Record the evidence and escalate persistent data issues without deleting history.",
        ],
      },
    ],
    note: "Do not expose credentials, authentication secrets, or private student information in screenshots or support messages.",
  },
];
