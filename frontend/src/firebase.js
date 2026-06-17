// Firebase Auth Mock or Real integration wrapper
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
    if (isConfigured && auth) {
      return firebaseOnAuthStateChanged(auth, callback);
    } else {
      mockListeners.push(callback);
      // Immediately notify current mock state
      setTimeout(() => callback(mockUser), 100);
      return () => {
        console.log("firebase.js: mock listener unsubscribed");
        mockListeners = mockListeners.filter(l => l !== callback);
      };
    }
  },

  signInWithEmail: async (email, password) => {
    if (isConfigured && auth) {
      const userCredential = await signInWithEmailAndPassword(auth, email, password);
      return userCredential.user;
    } else {
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

  signUpWithEmail: async (email, password) => {
    if (isConfigured && auth) {
      const userCredential = await createUserWithEmailAndPassword(auth, email, password);
      return userCredential.user;
    } else {
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
    if (isConfigured && auth && googleProvider) {
      const userCredential = await signInWithPopup(auth, googleProvider);
      return userCredential.user;
    } else {
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
    if (isConfigured && auth) {
      await firebaseSignOut(auth);
    } else {
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
    if (isConfigured && auth && auth.currentUser) {
      return await auth.currentUser.getIdToken();
    } else {
      return mockUser ? mockUser.uid : "mock-user-123";
    }
  }
};
