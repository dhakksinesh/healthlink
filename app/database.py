
import logging
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import Column, DateTime, Float, Integer, String, create_engine
from sqlalchemy.orm import Session, declarative_base, sessionmaker

from shared.config import Settings

logger = logging.getLogger("healthlink.database")

Base = declarative_base()

class DoctorModel(Base):

    __tablename__ = "doctors"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(200), nullable=False)
    specialty = Column(String(100), nullable=False)
    experience_years = Column(Integer, nullable=False)
    rating = Column(Float, nullable=False)
    availability = Column(String(100), nullable=False)
    location = Column(String(200), nullable=False)
    email = Column(String(200), nullable=True)
    phone = Column(String(20), nullable=True)
    qualifications = Column(String(500), nullable=True)
    languages = Column(String(200), nullable=True)
    consultation_type = Column(String(100), nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

class AppointmentModel(Base):

    __tablename__ = "appointments"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(100), nullable=False, index=True)
    doctor_name = Column(String(200), nullable=False)
    specialty = Column(String(100), nullable=False)
    appointment_date = Column(String(10), nullable=False)
    appointment_time = Column(String(5), nullable=False)
    status = Column(String(20), nullable=False, default="scheduled")
    reminder = Column(String(500), nullable=True)
    notes = Column(String(500), nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

class DatabaseManager:


    def __init__(self, settings: Settings):
        self.settings = settings

        if "sqlite" in settings.database_url:
            self.engine = create_engine(
                settings.database_url,
                echo=settings.db_echo,
                connect_args={"check_same_thread": False},
            )
        else:
            self.engine = create_engine(
                settings.database_url,
                echo=settings.db_echo,
                pool_size=settings.db_pool_size,
                max_overflow=settings.db_max_overflow,
                pool_pre_ping=True,
                pool_recycle=settings.db_pool_recycle_seconds,
            )

        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
        self._initialized = False

    def initialize_database(self) -> None:
        if not self._initialized:
            Base.metadata.create_all(bind=self.engine)
            logger.info("Database tables created/verified")
            self._initialized = True

    def get_session(self) -> Session:
        return self.SessionLocal()

    @contextmanager
    def session_scope(self):
        session = self.get_session()
        try:
            yield session
            session.commit()
        except Exception as e:
            session.rollback()
            logger.error(f"Database session error: {e}", exc_info=True)
            raise
        finally:
            session.close()

_db_manager: DatabaseManager | None = None

def get_db_manager(settings: Settings) -> DatabaseManager:
    global _db_manager
    if _db_manager is None:
        _db_manager = DatabaseManager(settings)
        _db_manager.initialize_database()
    return _db_manager

def reset_db_manager() -> None:

    global _db_manager
    if _db_manager is not None:
        try:
            _db_manager.engine.dispose()
        except Exception:
            pass
    _db_manager = None



def get_all_doctors(session: Session) -> list[DoctorModel]:
    return session.query(DoctorModel).all()

def get_doctors_by_specialty(session: Session, specialty: str) -> list[DoctorModel]:
    return session.query(DoctorModel).filter(
        DoctorModel.specialty.ilike(f"%{specialty}%")
    ).all()

def get_doctor_by_id(session: Session, doctor_id: int) -> DoctorModel | None:
    return session.query(DoctorModel).filter(DoctorModel.id == doctor_id).first()

def get_doctor_by_name(session: Session, name: str) -> DoctorModel | None:
    return session.query(DoctorModel).filter(DoctorModel.name == name).first()

def get_specialties(session: Session) -> list[str]:
    rows = session.query(DoctorModel.specialty).distinct().all()
    return sorted({r[0] for r in rows})

def seed_doctors(session: Session, doctors_data: list[dict[str, Any]]) -> None:

    existing_count = session.query(DoctorModel).count()
    if existing_count > 0:
        logger.info(f"Database already contains {existing_count} doctors, skipping seed")
        return

    columns = set(DoctorModel.__table__.columns.keys())
    for data in doctors_data:
        filtered = {k: v for k, v in data.items() if k in columns}
        session.add(DoctorModel(**filtered))

    session.commit()
    logger.info(f"Seeded database with {len(doctors_data)} doctors")



def create_appointment(
    session: Session,
    user_id: str,
    doctor_name: str,
    specialty: str,
    appointment_date: str,
    appointment_time: str,
    reminder: str | None = None,
    notes: str | None = None,
) -> AppointmentModel:
    appointment = AppointmentModel(
        user_id=user_id,
        doctor_name=doctor_name,
        specialty=specialty,
        appointment_date=appointment_date,
        appointment_time=appointment_time,
        status="scheduled",
        reminder=reminder,
        notes=notes,
    )
    session.add(appointment)
    session.flush()
    return appointment

def get_appointments_for_user(session: Session, user_id: str) -> list[AppointmentModel]:
    return (
        session.query(AppointmentModel)
        .filter(AppointmentModel.user_id == user_id)
        .order_by(AppointmentModel.appointment_date.desc())
        .all()
    )

def get_appointment_by_id(session: Session, appointment_id: int) -> AppointmentModel | None:
    return session.query(AppointmentModel).filter(AppointmentModel.id == appointment_id).first()

def update_appointment_status(session: Session, appointment_id: int, status: str) -> AppointmentModel | None:
    appointment = get_appointment_by_id(session, appointment_id)
    if appointment is None:
        return None
    appointment.status = status
    session.flush()
    return appointment
