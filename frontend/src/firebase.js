// Firebase Auth Mock or Real integration wrapper with automatic graceful fallback
import { initializeApp } from 'firebase/app';
import {
  getAuth,
  signInWithEmailAndPassword,
  createUserWithEmailAndPassword,
  signInWithPopup,
  GoogleAuthProvider,
  signOut as firebaseSignOut,
  onAuthStateChanged as firebaseOnAuthStateChanged
} from 'firebase/auth';

const firebaseConfig = {
  apiKey: import.meta.env.VITE_FIREBASE_API_KEY || "",
  authDomain: import.meta.env.VITE_FIREBASE_AUTH_DOMAIN || "",
  projectId: import.meta.env.VITE_FIREBASE_PROJECT_ID || "",
  storageBucket: import.meta.env.VITE_FIREBASE_STORAGE_BUCKET || "",
  messagingSenderId: import.meta.env.VITE_FIREBASE_MESSAGING_SENDER_ID || "",
  appId: import.meta.env.VITE_FIREBASE_APP_ID || ""
};

// Enable real Firebase Auth if API key is present and not a placeholder
const isConfigured = !!(firebaseConfig.apiKey && firebaseConfig.apiKey !== "your_api_key");

let app;
let auth;
let googleProvider;

if (isConfigured) {
  try {
    app = initializeApp(firebaseConfig);
    auth = getAuth(app);
    googleProvider = new GoogleAuthProvider();
  } catch (error) {
    console.error("Error initializing real Firebase:", error);
  }
}

// Unified state management for both real and mock auth
let activeUser = null;
let unifiedListeners = [];

const setAndNotifyUser = (user) => {
  activeUser = user;
  unifiedListeners.forEach(listener => {
    try {
      listener(user);
    } catch (e) {
      console.error("Error in auth listener:", e);
    }
  });
};

// Listen to real Firebase auth changes
if (isConfigured && auth) {
  try {
    firebaseOnAuthStateChanged(auth, (firebaseUser) => {
      if (!authService.isMock) {
        console.log("firebase.js: Real Firebase Auth state change:", firebaseUser ? firebaseUser.email : "logged out");
        setAndNotifyUser(firebaseUser);
      }
    });
  } catch (error) {
    console.error("Error setting up real Firebase auth listener:", error);
  }
}

// Helper mock functions
const mockSignInWithEmail = (email) => {
  const mockUser = {
    uid: `mock-${email.split('@')[0]}`,
    email: email,
    displayName: email.split('@')[0].toUpperCase(),
    photoURL: ""
  };
  setAndNotifyUser(mockUser);
  return mockUser;
};

const mockSignInWithGoogle = () => {
  const mockUser = {
    uid: "mock-google-user",
    email: "google.eco@gmail.com",
    displayName: "Google Eco-Warrior",
    photoURL: ""
  };
  setAndNotifyUser(mockUser);
  return mockUser;
};

export const authService = {
  isMock: !isConfigured,

  onAuthStateChanged: (callback) => {
    console.log("firebase.js: onAuthStateChanged called, isMock:", authService.isMock);
    unifiedListeners.push(callback);

    // In pure mock mode, auto-login with default credentials on load for zero-friction testing
    if (authService.isMock && !activeUser) {
      activeUser = {
        uid: "mock-user-123",
        email: "eco.challenger@domain.com",
        displayName: "Green Warrior",
        photoURL: ""
      };
    }

    // Immediately notify of current state
    setTimeout(() => callback(activeUser), 100);

    return () => {
      unifiedListeners = unifiedListeners.filter(l => l !== callback);
    };
  },

  signInWithEmail: async (email, password) => {
    if (!authService.isMock && auth) {
      try {
        const userCredential = await signInWithEmailAndPassword(auth, email, password);
        return userCredential.user;
      } catch (error) {
        console.warn("Real Firebase Auth sign-in failed:", error.code, error.message);
        if (error.code === 'auth/configuration-not-found' || error.code === 'auth/operation-not-allowed') {
          console.warn("Real Firebase Auth is not enabled in the Firebase Console. Falling back to Mock Auth gracefully.");
          authService.isMock = true;
          return mockSignInWithEmail(email);
        }
        throw error;
      }
    } else {
      return mockSignInWithEmail(email);
    }
  },

  signUpWithEmail: async (email, password) => {
    if (!authService.isMock && auth) {
      try {
        const userCredential = await createUserWithEmailAndPassword(auth, email, password);
        return userCredential.user;
      } catch (error) {
        console.warn("Real Firebase Auth sign-up failed:", error.code, error.message);
        if (error.code === 'auth/configuration-not-found' || error.code === 'auth/operation-not-allowed') {
          console.warn("Real Firebase Auth is not enabled in the Firebase Console. Falling back to Mock Auth gracefully.");
          authService.isMock = true;
          return mockSignInWithEmail(email);
        }
        throw error;
      }
    } else {
      return mockSignInWithEmail(email);
    }
  },

  signInWithGoogle: async () => {
    if (!authService.isMock && auth && googleProvider) {
      try {
        const userCredential = await signInWithPopup(auth, googleProvider);
        return userCredential.user;
      } catch (error) {
        console.warn("Real Firebase Google sign-in failed:", error.code, error.message);
        if (error.code === 'auth/configuration-not-found' || error.code === 'auth/operation-not-allowed') {
          console.warn("Real Firebase Google Auth is not enabled in the Firebase Console. Falling back to Mock Auth gracefully.");
          authService.isMock = true;
          return mockSignInWithGoogle();
        }
        throw error;
      }
    } else {
      return mockSignInWithGoogle();
    }
  },

  signOut: async () => {
    if (!authService.isMock && auth) {
      try {
        await firebaseSignOut(auth);
        setAndNotifyUser(null);
      } catch (error) {
        console.error("Real Firebase signOut failed:", error);
        setAndNotifyUser(null);
      }
    } else {
      setAndNotifyUser(null);
    }
  },

  getAuthToken: async () => {
    if (!authService.isMock && auth && auth.currentUser) {
      try {
        return await auth.currentUser.getIdToken();
      } catch (error) {
        console.warn("Could not get real auth token:", error);
        return activeUser ? activeUser.uid : "mock-user-123";
      }
    }
    return activeUser ? activeUser.uid : "mock-user-123";
  }
};
