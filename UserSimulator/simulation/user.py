import random
import numpy as np
from UserSimulator.utils.logger import logger

class User:
    def __init__(self, user_id, node, speed_normal, speed_alert):
        self.user_id = user_id
        self.current_node = node['node_id']
        self.x = int(round(np.random.uniform(node['x1'], node['x2'])))
        self.y = int(round(np.random.uniform(node['y1'], node['y2'])))
        self.z = int(round(np.random.uniform(node['z1'], node['z2'])))

        self.state = "normale"  # "normale", "allerta", "salvo"
        self.speed_normal = speed_normal
        self.speed_alert = speed_alert
        self.speed = speed_normal
        
        self.event = None
        
        self.evacuation_path = []  # lista di arc_id
        self.moving_along_arc = False
        self.arc_progress = 0.0
        self.movement_direction = 1  # +1 o -1 per indicare direzione su arco
        self.blocked = False

        self.failed_directions = set()
        self.stuck_ticks = 0
        self.prev_node_id = self.current_node
        
        logger.info(f"[INIT] User {self.user_id} initialized at node {self.current_node} pos=({self.x:.2f},{self.y:.2f},{self.z:.2f}) state={self.state}")

    def get_position_message(self):
        return {
            "user_id": self.user_id,
            "x": int(round(self.x)),
            "y": int(round(self.y)),
            "z": int(round(self.z)),
            "node_id": self.current_node,
            "event": self.event
        }

    def update_position(self, arcs, nodes, dt):
        try:
            if self.state == "in_attesa_percorso":
                # Utente fermo, non si muove finché non riceve percorso
                logger.debug(f"User {self.user_id} in ATTESA PERCORSO, fermo")
                return False

            elif self.state == "allerta":
                if self.evacuation_path:
                    completed = self._move_along_path(arcs, nodes, dt)
                    return completed
                else:
                    # In allerta ma senza percorso, utente fermo (o si può modificare se vuoi)
                    logger.debug(f"User {self.user_id} in ALLERTA state without path, not moving")
                    return False
            
            elif self.state == "normale":
                self._move_free(arcs, nodes, dt)
                return False
            
            else:
                # Stato salvo o altri, non si muove
                logger.debug(f"User {self.user_id} in state {self.state}, no movement")
                return False

        except Exception as e:
            logger.error(f"User {self.user_id} update_position error: {e}", exc_info=True)
            return False

    def _get_adjacent_nodes(self, node_id, arcs):
        """Restituisce lista di nodi direttamente connessi a node_id"""
        node_id = int(node_id)
        adjacent = set()
        for arc in arcs:
            if arc['initial_node'] == node_id:
                adjacent.add(arc['final_node'])
            elif arc['final_node'] == node_id:
                adjacent.add(arc['initial_node'])
        return list(adjacent)

    def _get_node_by_id(self, node_id, nodes):
        """Restituisce il dizionario del nodo dato l'ID"""
        for node in nodes:
            if node['node_id'] == node_id:
                return node
        return None


    def _move_free(self, arcs, nodes, dt):
        max_attempts = 10
        moved = False

        # Controlla se l'utente è bloccato da troppi tick
        if self.stuck_ticks >= 5:
            logger.debug(f"[FALLBACK_TRIGGER] User {self.user_id} stuck in node {self.current_node} for {self.stuck_ticks} ticks")
            adjacent_nodes = self._get_adjacent_nodes(self.current_node, arcs)
            random.shuffle(adjacent_nodes)

            for adj_node in adjacent_nodes:
                if (self.current_node, adj_node) in self.failed_directions:
                    continue
                node_data = self._get_node_by_id(adj_node, nodes)
                if node_data:
                    self.x = int(round(np.random.uniform(node_data['x1'], node_data['x2'])))
                    self.y = int(round(np.random.uniform(node_data['y1'], node_data['y2'])))
                    self.z = int(round(np.random.uniform(node_data['z1'], node_data['z2'])))
                    self.current_node = adj_node
                    self.stuck_ticks = 0
                    self.prev_node_id = adj_node
                    logger.debug(f"[FALLBACK_MOVE] User {self.user_id} moved from stuck node to adjacent node {adj_node}")
                    return
            logger.debug(f"[STUCK_NO_ADJACENT] User {self.user_id} could not escape from node {self.current_node}")
            return

        for attempt in range(max_attempts):
            dx = np.random.randint(-15, 16)
            dy = np.random.randint(-15, 16)
            dz = np.random.randint(-2, 3)

            new_x = self.x + dx
            new_y = self.y + dy
            new_z = self.z + dz

            target_node = self._find_containing_node(new_x, new_y, new_z, nodes)

            if target_node is not None:
                self.x = new_x
                self.y = new_y
                self.z = new_z
                self.current_node = target_node
                moved = True
                logger.debug(f"User {self.user_id} moved free to node {target_node}")
                break

            # A metà dei tentativi, prova a fare jitter nel nodo corrente
            if attempt == max_attempts // 2:
                node_data = self._get_node_by_id(self.current_node, nodes)
                if node_data:
                    self.x = int(round(np.random.uniform(node_data['x1'], node_data['x2'])))
                    self.y = int(round(np.random.uniform(node_data['y1'], node_data['y2'])))
                    self.z = int(round(np.random.uniform(node_data['z1'], node_data['z2'])))
                    self.current_node = self.current_node  # invariato
                    moved = True
                    logger.debug(f"User {self.user_id} jittered inside node {self.current_node}")
                    break

        # Aggiorna contatore stuck
        if self.current_node == self.prev_node_id:
            self.stuck_ticks += 1
        else:
            self.stuck_ticks = 0
            self.prev_node_id = self.current_node


    def _find_containing_node(self, x, y, z, nodes):
        for node in nodes:
            if node['x1'] <= x <= node['x2'] and \
            node['y1'] <= y <= node['y2'] and \
            node['z1'] <= z <= node['z2']:
                return node['node_id']
        return None


    def _is_connected(self, node_a, node_b, arcs):
        node_a = int(node_a)
        node_b = int(node_b)
        for arc in arcs:
            try:
                if (int(arc['initial_node']) == node_a and int(arc['final_node']) == node_b) or \
                (int(arc['initial_node']) == node_b and int(arc['final_node']) == node_a):
                    return True
            except Exception as e:
                logger.warning(f"[ARC FORMAT ERROR] {arc} caused {e}")
        logger.debug(f"[NO ARC] No connection between {node_a} and {node_b}")
        return False

    def find_arc_by_id(self, arcs, arc_id):
        for arc in arcs:
            if arc['arc_id'] == arc_id:
                return arc
        return None

    def arc_length(self, arc):
        start = np.array([arc['x1'], arc['y1'], arc['z1']])
        end = np.array([arc['x2'], arc['y2'], arc['z2']])
        return np.linalg.norm(end - start)

    def position_along_arc(self, arc, progress, reverse=False):
        start = np.array([arc['x1'], arc['y1'], arc['z1']])
        end = np.array([arc['x2'], arc['y2'], arc['z2']])
        if reverse:
            start, end = end, start
        return start + progress * (end - start)

    def is_position_inside_node(self, pos, node):
        x, y, z = pos
        return (node['x1'] <= x <= node['x2'] and
                node['y1'] <= y <= node['y2'] and
                node['z1'] <= z <= node['z2'])

    def _move_along_path(self, arcs, nodes, dt):
        if not self.evacuation_path:
            logger.debug(f"User {self.user_id} evacuation_path vuota, utente già salvo o non in movimento")
            self.moving_along_arc = False
            return False
        
        if not self.moving_along_arc:
            self.moving_along_arc = True
            self.arc_progress = 0.0

        current_arc_id = self.evacuation_path[0]
        arc = self.find_arc_by_id(arcs, current_arc_id)
        if arc is None:
            logger.warning(f"User {self.user_id} arc {current_arc_id} not found")
            self.moving_along_arc = False
            return False
        
        # Verifico se current_node è uno dei nodi dell'arco
        if self.current_node not in (arc['initial_node'], arc['final_node']):
            # Provo a forzare posizione se vicino ai nodi arco
            pos = np.array([self.x, self.y, self.z])
            p1 = np.array([arc['x1'], arc['y1'], arc['z1']])
            p2 = np.array([arc['x2'], arc['y2'], arc['z2']])
            dist_to_p1 = np.linalg.norm(pos - p1)
            dist_to_p2 = np.linalg.norm(pos - p2)
            snap_threshold = 5.0
            
            if min(dist_to_p1, dist_to_p2) < snap_threshold:
                self.current_node = arc['initial_node'] if dist_to_p1 < dist_to_p2 else arc['final_node']
                logger.debug(f"User {self.user_id} snapped to node {self.current_node} on arc {current_arc_id}")
            else:
                logger.warning(f"User {self.user_id} current_node {self.current_node} not connected to arc {current_arc_id}, waiting for update")
                self.moving_along_arc = False
                self.blocked =True
                
                return False
            

        # Determino la direzione: se sono su initial_node, muovo progress da 0->1; se su final_node, da 1->0
        reverse = (self.current_node == arc['final_node'])
        self.movement_direction = -1 if reverse else 1

        length = self.arc_length(arc)
        if length == 0:
            logger.warning(f"User {self.user_id} arc {current_arc_id} zero length")
            self.moving_along_arc = False
            return False

        # Aggiorno progress tenendo conto della direzione
        self.arc_progress += (self.speed * dt) / length * self.movement_direction
        self.arc_progress = max(0.0, min(1.0, self.arc_progress))

        pos = self.position_along_arc(arc, self.arc_progress, reverse)
        node = next(n for n in nodes if n['node_id'] == self.current_node)
        if not self.is_position_inside_node(pos, node):
            # Correggo posizione fuori nodo
            pos = np.array([
                np.clip(pos[0], node['x1'], node['x2']),
                np.clip(pos[1], node['y1'], node['y2']),
                np.clip(pos[2], node['z1'], node['z2']),
            ])
        self.x, self.y, self.z = map(lambda v: int(round(v)), pos)
        self.blocked = False

        logger.debug(f"User {self.user_id} moved along arc {current_arc_id} progress={self.arc_progress:.2f}")

        if (self.movement_direction == 1 and self.arc_progress >= 1.0) or (self.movement_direction == -1 and self.arc_progress <= 0.0):
            # Modifica importante: assegno current_node sempre al nodo FINALE dell'arco per evitare errori
            if self.movement_direction == 1:
                self.current_node = arc['final_node']
            else:
                self.current_node = arc['initial_node']

            self.evacuation_path.pop(0)
            self.moving_along_arc = False
            self.arc_progress = 0.0
            logger.info(f"User {self.user_id} completed arc {current_arc_id}, current_node set to {self.current_node}")

            if self.evacuation_path:
                # Posiziono utente sul nodo iniziale del prossimo arco
                next_arc_id = self.evacuation_path[0]
                next_arc = self.find_arc_by_id(arcs, next_arc_id)
                if next_arc is None:
                    logger.warning(f"User {self.user_id} next arc {next_arc_id} not found")
                    return False

                if self.current_node == next_arc['initial_node']:
                    new_pos = np.array([next_arc['x1'], next_arc['y1'], next_arc['z1']])
                elif self.current_node == next_arc['final_node']:
                    new_pos = np.array([next_arc['x2'], next_arc['y2'], next_arc['z2']])
                else:
                    logger.warning(f"User {self.user_id} node {self.current_node} does not match next arc {next_arc_id}")
                    return False

                node = next(n for n in nodes if n['node_id'] == self.current_node)
                if not self.is_position_inside_node(new_pos, node):
                    new_pos = np.array([
                        np.clip(new_pos[0], node['x1'], node['x2']),
                        np.clip(new_pos[1], node['y1'], node['y2']),
                        np.clip(new_pos[2], node['z1'], node['z2']),
                    ])
                self.x, self.y, self.z = new_pos
                return False
            else:
                # Percorso completato: posizione finale su nodo di arrivo (final_node)
                final_node_id = self.current_node
                final_node = next((n for n in nodes if n['node_id'] == final_node_id), None)
                if final_node:
                    # Posiziono esattamente al centro del nodo finale
                    self.x = (final_node['x1'] + final_node['x2']) / 2
                    self.y = (final_node['y1'] + final_node['y2']) / 2
                    self.z = (final_node['z1'] + final_node['z2']) / 2

                logger.info(f"User {self.user_id} reached end of evacuation path at node {final_node_id}")
                self.mark_as_salvo()
                return True
        
        self.moving_along_arc = True
        return False

    def mark_as_salvo(self):
        if self.state == "salvo":
        # Evito doppioni
            return
        self.evacuation_path.clear()
        self.moving_along_arc = False
        self.arc_progress = 0.0
        self.state = "salvo"
        self.speed = 0
        logger.info(f"User {self.user_id} evacuation completed, state set to SALVO")

        

    def set_evacuation_path(self, new_path):
        if new_path != self.evacuation_path:
            logger.info(f"User {self.user_id} received new evacuation path: {new_path}")
            self.evacuation_path = new_path.copy()
            self.moving_along_arc = False
            self.arc_progress = 0.0
            self.blocked = False
            if self.state != "allerta":
                self.state = "allerta"
                self.speed = self.speed_alert
                logger.info(f"User {self.user_id} state changed to ALLERTA")
        

    def set_state(self, new_state):
        if new_state != self.state:
            self.state = new_state
            self.speed = self.speed_alert if new_state == "allerta" else self.speed_normal
            logger.info(f"User {self.user_id} state changed to {new_state.upper()}")
            if new_state == "salvo":
                self.evacuation_path.clear()
                self.moving_along_arc = False
                self.arc_progress = 0.0
