import {
  getFirestore,
  doc,
  getDoc,
  setDoc,
  collection,
  collectionGroup,
  addDoc,
  getDocs,
  query,
  orderBy,
  limit,
  runTransaction,
  serverTimestamp
} from "https://www.gstatic.com/firebasejs/10.9.0/firebase-firestore.js";

const emptyProgress = () => ({
  xp: 0,
  level: 1,
  streak: 0,
  completed: [],
  goals: { day: 0, week: 0, month: 0 }
});

const dateKey = date => date.toISOString().slice(0, 10);

export function createCloudStore(app, user) {
  const db = getFirestore(app);
  const userRef = doc(db, "users", user.uid);
  const leaderRef = doc(db, "leaderboard", user.uid);

  async function readUser() {
    const snapshot = await getDoc(userRef);
    return snapshot.exists() ? snapshot.data() : null;
  }

  async function saveProfile(profile) {
    await setDoc(userRef, {
      uid: user.uid,
      email: user.email || null,
      displayName: profile.name || user.displayName || "Student",
      profile,
      updatedAt: serverTimestamp()
    }, { merge: true });
    await setDoc(leaderRef, {
      uid: user.uid,
      displayName: profile.name || user.displayName || "Student",
      xp: 0,
      level: 1,
      streak: 0,
      completedCount: 0,
      updatedAt: serverTimestamp()
    }, { merge: true });
  }

  async function getProfile() {
    return (await readUser())?.profile || null;
  }

  async function saveTodos(todos) {
    await setDoc(userRef, { todos, updatedAt: serverTimestamp() }, { merge: true });
  }

  async function getTodos() {
    return (await readUser())?.todos || [];
  }

  async function getProgress() {
    return (await readUser())?.progress || null;
  }

  async function seedProgress(progress) {
    const safe = { ...emptyProgress(), ...progress };
    await setDoc(userRef, { progress: safe, updatedAt: serverTimestamp() }, { merge: true });
    await setDoc(leaderRef, {
      uid: user.uid,
      displayName: (await readUser())?.displayName || user.displayName || "Student",
      xp: safe.xp || 0,
      level: safe.level || 1,
      streak: safe.streak || 0,
      completedCount: safe.completed?.length || 0,
      updatedAt: serverTimestamp()
    }, { merge: true });
    return safe;
  }

  async function awardQuest(questId, awardedXp) {
    const today = new Date();
    const todayKey = dateKey(today);
    const yesterday = new Date(today);
    yesterday.setDate(yesterday.getDate() - 1);
    let next;

    await runTransaction(db, async transaction => {
      const snapshot = await transaction.get(userRef);
      const data = snapshot.exists() ? snapshot.data() : {};
      const current = { ...emptyProgress(), ...(data.progress || {}) };
      if (current.completed.includes(questId)) {
        next = current;
        return;
      }
      const completed = [...current.completed, questId];
      const lastCompleted = current.lastCompleted || null;
      const streak = lastCompleted === todayKey
        ? current.streak
        : lastCompleted === dateKey(yesterday)
          ? current.streak + 1
          : 1;
      const xp = current.xp + Number(awardedXp || 0);
      const goals = {
        day: (current.goals?.day || 0) + 1,
        week: (current.goals?.week || 0) + 1,
        month: (current.goals?.month || 0) + 1
      };
      next = { ...current, xp, level: Math.floor(xp / 100) + 1, streak, completed, goals, lastCompleted: todayKey };
      transaction.set(userRef, { progress: next, updatedAt: serverTimestamp() }, { merge: true });
      transaction.set(leaderRef, {
        uid: user.uid,
        displayName: data.displayName || user.displayName || "Student",
        xp: next.xp,
        level: next.level,
        streak: next.streak,
        completedCount: next.completed.length,
        updatedAt: serverTimestamp()
      }, { merge: true });
    });
    return next;
  }

  async function getLeaderboard(maxRows = 20) {
    const snapshot = await getDocs(query(collection(db, "leaderboard"), orderBy("xp", "desc"), limit(maxRows)));
    return snapshot.docs.map(item => item.data());
  }

  async function track(type, details = {}) {
    await addDoc(collection(db, "users", user.uid, "events"), {
      type,
      details,
      createdAt: serverTimestamp()
    });
  }

  async function getAdminOverview() {
    if (user.uid !== "JuMiEQh6RrSXlVtHPNcjEwM95HD3") throw new Error("Admin access required.");
    const userSnapshot = await getDocs(query(collection(db, "users"), limit(100)));
    const users = userSnapshot.docs.map(item => item.data());
    const eventSnapshot = await getDocs(query(collectionGroup(db, "events"), orderBy("createdAt", "desc"), limit(25)));
    const events = eventSnapshot.docs.map(item => ({ id: item.id, ...item.data() }));
    return {
      users,
      events,
      totalProfiles: users.length,
      totalXp: users.reduce((sum, item) => sum + Number(item.progress?.xp || 0), 0),
      completedQuests: users.reduce((sum, item) => sum + Number(item.progress?.completed?.length || 0), 0)
    };
  }

  return { db, getProfile, saveProfile, getTodos, saveTodos, getProgress, seedProgress, awardQuest, getLeaderboard, track, getAdminOverview };
}

