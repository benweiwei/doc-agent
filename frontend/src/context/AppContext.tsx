import { createContext, useContext, useReducer, ReactNode, Dispatch } from "react";
import type { Document, BranchInfo, EditResponse, InteractionRecord, UnifiedDocument, StyleTemplateDTO } from "../types";

// --- State ---

export interface AppState {
  currentDocument: Document | null;
  currentBranch: string;
  documents: Document[];
  branches: BranchInfo[];
  allDocuments: UnifiedDocument[];
  branchFilter: string | null;
  isEditing: boolean;
  editResult: EditResponse | null;
  leftPanelOpen: boolean;
  rightPanelOpen: boolean;
  openTabs: Array<{ docId: string; title: string }>;
  activeTabId: string | null;
  unsavedChanges: Set<string>;
  streamingContent: string;
  isStreaming: boolean;
  interactionHistory: InteractionRecord[];
  styleTemplates: StyleTemplateDTO[];
  selectedStyle: string | null;
}

const initialState: AppState = {
  currentDocument: null,
  currentBranch: "main",
  documents: [],
  branches: [],
  allDocuments: [],
  branchFilter: null,
  isEditing: false,
  editResult: null,
  leftPanelOpen: true,
  rightPanelOpen: true,
  openTabs: [],
  activeTabId: null,
  unsavedChanges: new Set(),
  streamingContent: "",
  isStreaming: false,
  interactionHistory: [],
  styleTemplates: [],
  selectedStyle: null,
};

// --- Actions ---

export type AppAction =
  | { type: "SET_CURRENT_DOCUMENT"; payload: Document | null }
  | { type: "SET_CURRENT_BRANCH"; payload: string }
  | { type: "SET_DOCUMENTS"; payload: Document[] }
  | { type: "SET_BRANCHES"; payload: BranchInfo[] }
  | { type: "SET_ALL_DOCUMENTS"; documents: UnifiedDocument[] }
  | { type: "SET_BRANCH_FILTER"; branch: string | null }
  | { type: "SET_EDITING"; payload: boolean }
  | { type: "SET_EDIT_RESULT"; payload: EditResponse | null }
  | { type: "TOGGLE_LEFT_PANEL" }
  | { type: "TOGGLE_RIGHT_PANEL" }
  | { type: "OPEN_TAB"; payload: { docId: string; title: string } }
  | { type: "CLOSE_TAB"; payload: string }
  | { type: "SWITCH_TAB"; payload: string }
  | { type: "MARK_UNSAVED"; payload: string }
  | { type: "MARK_SAVED"; payload: string }
  | { type: "APPEND_STREAMING_CONTENT"; payload: string }
  | { type: "SET_STREAMING"; payload: boolean }
  | { type: "CLEAR_STREAMING" }
  | { type: "ADD_INTERACTION"; payload: InteractionRecord }
  | { type: "SET_INTERACTION_HISTORY"; history: InteractionRecord[] }
  | { type: "UPDATE_INTERACTION"; payload: { id: string } & Partial<InteractionRecord> }
  | { type: "SET_STYLE_TEMPLATES"; templates: StyleTemplateDTO[] }
  | { type: "SET_SELECTED_STYLE"; name: string | null };

// --- Reducer ---

function appReducer(state: AppState, action: AppAction): AppState {
  switch (action.type) {
    case "SET_CURRENT_DOCUMENT":
      return { ...state, currentDocument: action.payload };
    case "SET_CURRENT_BRANCH":
      return { ...state, currentBranch: action.payload, openTabs: [], activeTabId: null };
    case "SET_DOCUMENTS":
      return { ...state, documents: action.payload };
    case "SET_BRANCHES":
      return { ...state, branches: action.payload };
    case "SET_ALL_DOCUMENTS":
      return { ...state, allDocuments: action.documents };
    case "SET_BRANCH_FILTER":
      return { ...state, branchFilter: action.branch };
    case "SET_EDITING":
      return { ...state, isEditing: action.payload };
    case "SET_EDIT_RESULT":
      return { ...state, editResult: action.payload };
    case "TOGGLE_LEFT_PANEL":
      return { ...state, leftPanelOpen: !state.leftPanelOpen };
    case "TOGGLE_RIGHT_PANEL":
      return { ...state, rightPanelOpen: !state.rightPanelOpen };
    case "OPEN_TAB": {
      const exists = state.openTabs.find((t) => t.docId === action.payload.docId);
      if (exists) {
        return { ...state, activeTabId: action.payload.docId };
      }
      return {
        ...state,
        openTabs: [...state.openTabs, action.payload],
        activeTabId: action.payload.docId,
      };
    }
    case "CLOSE_TAB": {
      const newTabs = state.openTabs.filter((t) => t.docId !== action.payload);
      let newActiveTabId = state.activeTabId;
      if (state.activeTabId === action.payload) {
        const closedIdx = state.openTabs.findIndex((t) => t.docId === action.payload);
        if (newTabs.length > 0) {
          const nextIdx = Math.min(closedIdx, newTabs.length - 1);
          newActiveTabId = newTabs[nextIdx]!.docId;
        } else {
          newActiveTabId = null;
        }
      }
      return { ...state, openTabs: newTabs, activeTabId: newActiveTabId };
    }
    case "SWITCH_TAB":
      return { ...state, activeTabId: action.payload };
    case "MARK_UNSAVED": {
      const newUnsaved = new Set(state.unsavedChanges);
      newUnsaved.add(action.payload);
      return { ...state, unsavedChanges: newUnsaved };
    }
    case "MARK_SAVED": {
      const newUnsaved2 = new Set(state.unsavedChanges);
      newUnsaved2.delete(action.payload);
      return { ...state, unsavedChanges: newUnsaved2 };
    }
    case "APPEND_STREAMING_CONTENT":
      return { ...state, streamingContent: state.streamingContent + action.payload };
    case "SET_STREAMING":
      return { ...state, isStreaming: action.payload };
    case "CLEAR_STREAMING":
      return { ...state, streamingContent: "", isStreaming: false };
    case "ADD_INTERACTION":
      return { ...state, interactionHistory: [action.payload, ...state.interactionHistory] };
    case "SET_INTERACTION_HISTORY":
      return { ...state, interactionHistory: action.history };
    case "UPDATE_INTERACTION":
      return {
        ...state,
        interactionHistory: state.interactionHistory.map((item) =>
          item.id === action.payload.id ? { ...item, ...action.payload } : item
        ),
      };
    case "SET_STYLE_TEMPLATES":
      return { ...state, styleTemplates: action.templates };
    case "SET_SELECTED_STYLE":
      return { ...state, selectedStyle: action.name };
    default:
      return state;
  }
}

// --- Context ---

interface AppContextValue {
  state: AppState;
  dispatch: Dispatch<AppAction>;
}

const AppContext = createContext<AppContextValue | null>(null);

// --- Provider ---

export function AppProvider({ children }: { children: ReactNode }) {
  const [state, dispatch] = useReducer(appReducer, initialState);

  return (
    <AppContext.Provider value={{ state, dispatch }}>
      {children}
    </AppContext.Provider>
  );
}

// --- Hook ---

export function useAppContext(): AppContextValue {
  const context = useContext(AppContext);
  if (!context) {
    throw new Error("useAppContext must be used within an AppProvider");
  }
  return context;
}
