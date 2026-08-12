import { useState } from "react";

function App() {
  const [screen, setScreen] = useState("welcome");

  if (screen === "welcome") {
    return (
      <div style={styles.page}>
        <div style={styles.bgGlowOne} />
        <div style={styles.bgGlowTwo} />

        <div style={styles.welcomeCard}>
          <h1 style={styles.title}>JARVIS 2.0</h1>
          <p style={styles.subtitle}>Bienvenido, Gabo</p>

          <div style={styles.orb}>
            <div style={styles.orbCore} />
          </div>

          <button style={styles.primaryButton} onClick={() => setScreen("main")}>
            ENTRAR
          </button>
        </div>
      </div>
    );
  }

  return (
    <div style={styles.appShell}>
      <aside style={styles.sidebar}>
        <div style={styles.logo}>J</div>
        <button style={styles.sideButton}>⌂</button>
        <button style={styles.sideButton}>✦</button>
        <button style={styles.sideButton}>✎</button>
        <button style={styles.sideButton}>◇</button>
        <button style={styles.sideButton}>⚙</button>
      </aside>

      <main style={styles.main}>
        <h1 style={styles.mainTitle}>JARVIS 2.0</h1>

        <section style={styles.corePanel}>
          <div style={styles.bigOrb}>
            <div style={styles.bigOrbRing}>
              <div style={styles.bigOrbCore} />
            </div>
          </div>

          <h2 style={styles.statusText}>LISTO PARA CONVERSAR</h2>
        </section>
      </main>
    </div>
  );
}

const styles = {
  page: {
    width: "100vw",
    height: "100vh",
    background: "#020814",
    display: "flex",
    justifyContent: "center",
    alignItems: "center",
    overflow: "hidden",
    position: "relative",
    fontFamily: "Segoe UI, sans-serif",
  },
  bgGlowOne: {
    position: "absolute",
    width: 520,
    height: 520,
    borderRadius: "50%",
    background: "#073b55",
    filter: "blur(120px)",
    opacity: 0.55,
    left: "8%",
    top: "8%",
  },
  bgGlowTwo: {
    position: "absolute",
    width: 480,
    height: 480,
    borderRadius: "50%",
    background: "#2b1468",
    filter: "blur(140px)",
    opacity: 0.45,
    right: "6%",
    bottom: "4%",
  },
  welcomeCard: {
    width: 850,
    height: 560,
    borderRadius: 46,
    background: "rgba(3,18,38,0.92)",
    border: "1px solid rgba(103,247,255,0.75)",
    boxShadow: "0 0 70px rgba(103,247,255,0.22)",
    display: "flex",
    flexDirection: "column",
    alignItems: "center",
    justifyContent: "center",
    zIndex: 1,
  },
  title: {
    color: "#ecfeff",
    fontSize: 62,
    margin: 0,
    fontWeight: 900,
    letterSpacing: 3,
  },
  subtitle: {
    color: "#67f7ff",
    fontSize: 30,
    marginTop: 12,
    marginBottom: 40,
    fontWeight: 600,
  },
  orb: {
    width: 230,
    height: 230,
    borderRadius: "50%",
    background: "radial-gradient(circle,#0b4c75,#041020)",
    border: "2px solid #67f7ff",
    display: "flex",
    justifyContent: "center",
    alignItems: "center",
    boxShadow: "0 0 42px rgba(103,247,255,0.7)",
  },
  orbCore: {
    width: 118,
    height: 118,
    borderRadius: "50%",
    background: "#67f7ff",
    boxShadow: "0 0 60px #67f7ff",
  },
  primaryButton: {
    marginTop: 48,
    width: 230,
    height: 60,
    borderRadius: 18,
    border: "none",
    background: "#67f7ff",
    color: "#020814",
    fontSize: 18,
    fontWeight: 800,
    cursor: "pointer",
  },
  appShell: {
    width: "100vw",
    height: "100vh",
    background:
      "radial-gradient(circle at 20% 20%, #062a4a 0%, transparent 28%), radial-gradient(circle at 85% 80%, #24115a 0%, transparent 30%), #020814",
    display: "flex",
    fontFamily: "Segoe UI, sans-serif",
    overflow: "hidden",
  },
  sidebar: {
    width: 92,
    height: "100vh",
    background: "rgba(3,18,38,0.92)",
    borderRight: "1px solid rgba(103,247,255,0.2)",
    display: "flex",
    flexDirection: "column",
    alignItems: "center",
    paddingTop: 28,
    gap: 18,
  },
  logo: {
    color: "#67f7ff",
    fontSize: 42,
    fontWeight: 900,
    marginBottom: 20,
  },
  sideButton: {
    width: 54,
    height: 54,
    borderRadius: 16,
    border: "1px solid rgba(103,247,255,0.25)",
    background: "rgba(8,33,61,0.95)",
    color: "#67f7ff",
    fontSize: 24,
    cursor: "pointer",
  },
  main: {
    flex: 1,
    padding: "34px 56px 46px",
    display: "flex",
    flexDirection: "column",
    alignItems: "center",
  },
  mainTitle: {
    color: "#ecfeff",
    fontSize: 48,
    margin: 0,
    fontWeight: 900,
    letterSpacing: 2,
  },
  corePanel: {
    marginTop: 34,
    width: "100%",
    flex: 1,
    borderRadius: 46,
    background: "rgba(3,18,38,0.86)",
    border: "1px solid rgba(103,247,255,0.45)",
    boxShadow: "0 0 60px rgba(103,247,255,0.12)",
    display: "flex",
    flexDirection: "column",
    justifyContent: "center",
    alignItems: "center",
  },
  bigOrb: {
    width: 390,
    height: 390,
    borderRadius: "50%",
    background: "radial-gradient(circle,#0a3a5c,#031226 70%)",
    border: "2px solid rgba(155,92,255,0.85)",
    boxShadow: "0 0 80px rgba(103,247,255,0.35)",
    display: "flex",
    justifyContent: "center",
    alignItems: "center",
  },
  bigOrbRing: {
    width: 290,
    height: 290,
    borderRadius: "50%",
    border: "2px solid #67f7ff",
    display: "flex",
    justifyContent: "center",
    alignItems: "center",
    boxShadow: "0 0 45px rgba(103,247,255,0.35)",
  },
  bigOrbCore: {
    width: 150,
    height: 150,
    borderRadius: "50%",
    background: "#67f7ff",
    boxShadow: "0 0 70px #67f7ff",
  },
  statusText: {
    marginTop: 38,
    color: "#b7ecff",
    fontSize: 22,
    letterSpacing: 2,
  },
};

export default App;