import tempfile
import unittest
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.solicitudes.dominio import APROBADA, RECHAZADA, ResultadoPadron, Solicitud
from app.solicitudes.repositorio import SolicitudRow, SqlAlchemySolicitudes


class ConcurrentDecisionTests(unittest.TestCase):
    def test_a_second_decision_based_on_a_stale_read_cannot_overwrite_the_winner(self):
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / 'municipio.db'
            engine = create_engine(f'sqlite:///{database.as_posix()}')
            try:
                SolicitudRow.metadata.create_all(engine)
                with Session(engine) as first_session, Session(engine) as second_session:
                    first = SqlAlchemySolicitudes(first_session)
                    second = SqlAlchemySolicitudes(second_session)
                    created = first.agregar(Solicitud.presentar('tarifa-social', 'vecino', 'vecino1'))
                    first_read = first.obtener(created.id)
                    second_read = second.obtener(created.id)
                    approval = first_read.decidir(APROBADA, 'Verificación positiva', 'agente-1', ResultadoPadron.ELEGIBLE)
                    rejection = second_read.decidir(RECHAZADA, 'Intento simultáneo', 'agente-2', None)
                    self.assertEqual(first.guardar_si_pendiente(approval).estado, APROBADA)
                    self.assertIsNone(second.guardar_si_pendiente(rejection))
                    final = second.obtener(created.id)
                    self.assertEqual((final.estado, final.motivo, final.agente_id),
                                     (APROBADA, 'Verificación positiva', 'agente-1'))
            finally:
                engine.dispose()
