// A stand-in for Cloudflare D1, on Node's built-in SQLite, with the parts of
// the D1 API the handler uses: prepare().bind().first() / .all() / .run(),
// and db.batch() as one transaction. Tests only.
import { DatabaseSync } from "node:sqlite";

class Statement {
  constructor(db, sql, args = []) {
    this.db = db;
    this.sql = sql;
    this.args = args;
  }

  bind(...args) {
    return new Statement(this.db, this.sql, args);
  }

  async first() {
    return this.db.prepare(this.sql).get(...this.args) ?? null;
  }

  async all() {
    return { results: this.db.prepare(this.sql).all(...this.args), success: true, meta: {} };
  }

  async run() {
    return this._run();
  }

  _run() {
    const info = this.db.prepare(this.sql).run(...this.args);
    return { success: true,
      meta: { changes: Number(info.changes), last_row_id: Number(info.lastInsertRowid) } };
  }
}

export class D1 {
  constructor(path = ":memory:") {
    this.db = new DatabaseSync(path);
    this.queries = 0;
  }

  prepare(sql) {
    this.queries += 1;
    return new Statement(this.db, sql);
  }

  async batch(statements) {
    this.db.exec("BEGIN");
    try {
      const out = statements.map((s) => s._run());
      this.db.exec("COMMIT");
      return out;
    } catch (error) {
      this.db.exec("ROLLBACK");
      throw error;
    }
  }
}
