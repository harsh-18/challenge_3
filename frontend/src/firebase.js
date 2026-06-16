// Firebase Auth Mock or Real integration wrapper
// To enable real Firebase, populate variables in a .env.local file:
// VITE_FIREBASE_API_KEY=your_api_key
// VITE_FIREBASE_AUTH_DOMAIN=your_auth_domain

const firebaseConfig = {
  apiKey: import.meta.env.VITE_FIREBASE_API_KEY || "",
  authDomain: import.meta.env.VITE_FIREBASE_AUTH_DOMAIN || "",
  projectId: import.meta.env.VITE_FIREBASE_PROJECT_ID || "",
  storageBucket: import.meta.env.VITE_FIREBASE_STORAGE_BUCKET || "",
  messagingSenderId: import.meta.env.VITE_FIREBASE_MESSAGING_SENDER_ID || "",
  appId: import.meta.env.VITE_FIREBASE_APP_ID || ""
};

const isConfigured = false; // Always run in Mock Auth mode for zero-friction local/production testing

// In-Memory Mock Auth State for local-only testing
let mockUser = {
  uid: "mock-user-123",
  email: "eco.challenger@domain.com",
  displayName: "Green Warrior",
  photoURL: ""
};

let mockListeners = [];

const notifyListeners = (user) => {
  mockListeners.forEach(listener => listener(user));
};

export const authService = {
  isMock: !isConfigured,

  onAuthStateChanged: (callback) => {
    console.log("firebase.js: onAuthStateChanged called, isConfigured:", isConfigured);
    if (!isConfigured) {
      mockListeners.push(callback);
      // Immediately notify current mock state
      setTimeout(() => callback(mockUser), 100);
      return () => {
        console.log("firebase.js: mock listener unsubscribed");
        mockListeners = mockListeners.filter(l => l !== callback);
      };
    } else {
      console.log("firebase.js: real firebase auth requested but not implemented");
      return () => { };
    }
  },

  signInWithEmail: async (email, password) => {
    if (!isConfigured) {
      // Mock log in
      return new Promise((resolve) => {
        setTimeout(() => {
          mockUser = {
            uid: `mock-${email.split('@')[0]}`,
            email: email,
            displayName: email.split('@')[0].toUpperCase(),
            photoURL: ""
          };
          notifyListeners(mockUser);
          resolve(mockUser);
        }, 600);
      });
    }
    // Real implementation would call signInWithEmailAndPassword
  },

  signUpWithEmail: async (email, password) => {
    if (!isConfigured) {
      return new Promise((resolve) => {
        setTimeout(() => {
          mockUser = {
            uid: `mock-${email.split('@')[0]}`,
            email: email,
            displayName: email.split('@')[0].toUpperCase(),
            photoURL: ""
          };
          notifyListeners(mockUser);
          resolve(mockUser);
        }, 600);
      });
    }
  },

  signInWithGoogle: async () => {
    if (!isConfigured) {
      return new Promise((resolve) => {
        setTimeout(() => {
          mockUser = {
            uid: "mock-google-user",
            email: "google.eco@gmail.com",
            displayName: "Google Eco-Warrior",
            photoURL: ""
          };
          notifyListeners(mockUser);
          resolve(mockUser);
        }, 600);
      });
    }
  },

  signOut: async () => {
    if (!isConfigured) {
      return new Promise((resolve) => {
        setTimeout(() => {
          mockUser = null;
          notifyListeners(null);
          resolve();
        }, 300);
      });
    }
  },

  getAuthToken: async () => {
    if (!isConfigured) {
      // In mock mode, the mock uid is passed as the token directly
      return mockUser ? mockUser.uid : "";
    }
    // Real Firebase: return await auth.currentUser.getIdToken()
    return "mock-user-123";
  }
};
